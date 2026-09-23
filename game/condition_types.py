"""Frozen records for NeuroStudio's existing condition presentation document.

The renderer consumes appearance and transition fields. Relationship metadata
is retained as authoring data; it does not install or simulate game rules.
"""

from pathlib import Path
from types import MappingProxyType
from typing import Annotated, Literal, Mapping

from pydantic import BaseModel, ConfigDict, Field, field_serializer, model_validator

from dnd.core.content.identities import ContentRef
from dnd.core.creature_types import DamageType


Color = Annotated[int, Field(ge=0, le=0xFFFFFF)]
Name = Annotated[str, Field(min_length=1)]
Alpha = Annotated[float, Field(ge=0, le=1)]
Duration = Annotated[float, Field(ge=0)]
Priority = Annotated[int, Field(ge=-1000, le=1000)]
LifeStage = Literal["alive", "dying", "stable", "dead"]
Activity = Literal["idle", "move", "jump", "forced_move", "attack", "cast", "act", "hit"]
StudioEquipmentSlot = Literal[
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
    attachment: Literal["body", "ground", "head", "face"]
    offsetX: float = 0
    offsetY: float = 0
    opacity: Alpha = 1.
    activeDuring: tuple[Activity, ...]
    startOffsetMs: Duration = 0
    fadeInMs: Duration = 0
    priority: Priority
    colors: ConditionColors
    drawOrder: Literal["behind_body", "in_front_of_body"] = "in_front_of_body"
    lifeStates: tuple[LifeStage, ...] = ("alive", "dying", "stable", "dead")
    whenEnergyType: DamageType | None = None


class ConditionTransitionEffect(_Record):
    id: Name
    assetId: Name
    category: Name
    animation: Name
    attachment: Literal["body", "ground", "head", "face"]
    offsetX: float = 0
    offsetY: float = 0
    opacity: Alpha = 1.
    priority: Priority
    colors: ConditionColors
    durationMs: Duration
    startOffsetMs: Duration = 0
    drawOrder: Literal["behind_body", "in_front_of_body"] = "in_front_of_body"
    lifeStates: tuple[LifeStage, ...] = ("alive", "dying", "stable", "dead")


class ConditionActivation(_Record):
    trigger: Literal["owner_turn_start"]
    effects: tuple[ConditionTransitionEffect, ...]


class ConditionBodyColor(_Record):
    tintRgb: Color | None
    saturation: Annotated[float, Field(ge=0, le=2)]
    brightness: Annotated[float, Field(ge=0.25, le=2)]


class ConditionEquipmentModifier(_Record):
    id: Name
    slots: tuple[StudioEquipmentSlot, ...]
    alphaMultiplier: Alpha
    tintRgb: Color | None
    saturation: Annotated[float, Field(ge=0, le=2)]
    brightness: Annotated[float, Field(ge=0.25, le=2)]
    priority: Priority


class ConditionAppearanceLayer(_Record):
    id: Name
    slot: StudioEquipmentSlot
    category: Name
    tint: Color
    tint2: Color | None = None
    tint3: Color | None = None
    priority: Priority


class ConditionLabel(_Record):
    text: Name
    color: Color


class ConditionBodyScale(_Record):
    enlarge: Annotated[float, Field(gt=0)]
    reduce: Annotated[float, Field(gt=0)]


class BodyWave(_Record):
    amplitudePx: float
    rowFrequency: float
    timeFrequency: float


class BodyContour(_Record):
    offset: tuple[float, float]
    opacity: Alpha
    oscillation: tuple[float, float] = (0., 0.)
    frequency: float = 0.


class BodyTrail(_Record):
    ageMs: Annotated[float, Field(gt=0, le=240)]
    opacity: Alpha


class ConditionBodyDistortion(_Record):
    palette: tuple[Color, Color, Color, Color]
    paletteMaximum: Annotated[float, Field(gt=0)] = 170.
    waves: tuple[BodyWave, ...]
    bandHeightPx: Annotated[int, Field(ge=1)]
    bodyOpacity: Alpha
    contours: tuple[BodyContour, ...]
    trails: tuple[BodyTrail, ...]


class ConditionLiveCopies(_Record):
    slots: tuple[tuple[float, float], ...]
    palette: tuple[Color, Color, Color, Color]
    paletteMaximum: Annotated[float, Field(gt=0)] = 170.
    opacity: Alpha
    emergeMs: Duration
    dissipateMs: Duration
    # Local body alpha modulation, independent of world motion or actor facing.
    waveFrequency: tuple[float, float]
    waveSpeed: tuple[float, float]
    minimumOpacity: Alpha
    secondaryRowFrequency: float = .12
    slotPhase: float = 4.
    layers: tuple[ConditionLayer, ...] = ()
    applicationEffects: tuple[ConditionTransitionEffect, ...] = ()
    removalEffects: tuple[ConditionTransitionEffect, ...] = ()


class ConditionPersistent(_Record):
    alphaMultiplier: Alpha
    bodyColor: ConditionBodyColor | None
    # Hold the final frame of a mapped rig clip when no action owns the body.
    bodyPose: Name | None = None
    label: ConditionLabel | None = None
    bodyScale: ConditionBodyScale | None = None
    liveCopies: ConditionLiveCopies | None = None
    bodyDistortion: ConditionBodyDistortion | None = None
    equipmentModifiers: tuple[ConditionEquipmentModifier, ...]
    appearanceLayers: tuple[ConditionAppearanceLayer, ...]
    layers: tuple[ConditionLayer, ...]


class ConditionBodyAnimation(_Record):
    bodyClip: Name
    bodyPlaybackSpeed: Annotated[float, Field(gt=0)] = 1.0
    reversed: bool = False


class ConditionTransition(_Record):
    durationMs: Duration
    feedbackEnabled: bool
    feedbackColor: Color
    effects: tuple[ConditionTransitionEffect, ...]
    bodyAnimation: ConditionBodyAnimation | None = None


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
    activation: ConditionActivation | None = None
    reactionCastBinding: Name | None = None
    interceptionEffectsByDirection: Mapping[
        Literal["N", "NE", "E", "SE", "S", "SW", "W", "NW"], tuple[ConditionTransitionEffect, ...]
    ] = Field(default_factory=dict)

    @field_serializer("interceptionEffectsByDirection")
    def serialize_interceptions(self, value):
        return dict(value)

    @model_validator(mode="after")
    def validate_state_only(self) -> "ConditionRecipe":
        object.__setattr__(self, "interceptionEffectsByDirection", MappingProxyType(dict(self.interceptionEffectsByDirection)))
        if self.disposition == "state_only":
            persistent = self.persistent
            if (self.classification.visualIntensity not in ("state_only", "icon_only")
                    or any(domain not in ("none", "hud_only") for domain in self.classification.presentationDomains)
                    or persistent.alphaMultiplier != 1 or persistent.bodyColor is not None
                    or persistent.bodyPose is not None or persistent.label is not None
                    or persistent.bodyScale is not None or persistent.liveCopies is not None
                    or persistent.bodyDistortion is not None
                    or persistent.equipmentModifiers or persistent.appearanceLayers or persistent.layers
                    or self.application.effects or self.removal.effects or self.activation is not None
                    or self.reactionCastBinding is not None
                    or self.interceptionEffectsByDirection
                    or self.application.bodyAnimation is not None or self.removal.bodyAnimation is not None):
                raise ValueError("state_only condition recipes require neutral appearance and HUD/none classification")
        return self


class ConditionFile(_Record):
    schema_id: Literal["neuroclient.conditionPresentationRecipes"] = Field(alias="schema")
    version: Literal[12]
    recipes: tuple[ConditionRecipe, ...]


class ConditionBodyPresentation(_Record):
    bodyPose: Name | None = None
    label: ConditionLabel | None = None
    applicationBody: ConditionBodyAnimation | None = None
    removalBody: ConditionBodyAnimation | None = None


class ConditionOverrides(_Record):
    schema_id: Literal["dnd.conditionPresentationOverrides"] = Field(alias="schema")
    version: Literal[1]
    conditions: dict[str, ConditionBodyPresentation]


def load_condition_recipes(path: Path, *, overrides: Path | None = None,
                           local: Path | None = None) -> Mapping[str, ConditionRecipe]:
    """Bind current engine behavior IDs to exact source content IDs, not labels."""
    document = ConditionFile.model_validate_json(path.read_text(encoding="utf-8"))
    recipes: dict[str, ConditionRecipe] = {}
    for recipe in document.recipes:
        identity = recipe.definitionRef.content_id
        if identity in recipes:
            raise ValueError(f"ambiguous condition behavior identity: {identity}")
        recipes[identity] = recipe
    if local is not None:
        authored = ConditionFile.model_validate_json(local.read_text(encoding="utf-8"))
        local_identities: set[str] = set()
        for recipe in authored.recipes:
            identity = recipe.definitionRef.content_id
            if identity in local_identities:
                raise ValueError(f"ambiguous local condition behavior identity: {identity}")
            local_identities.add(identity)
            if identity in recipes and recipes[identity].definitionRef != recipe.definitionRef:
                raise ValueError(f"local condition definitionRef disagrees with source: {identity}")
            recipes[identity] = recipe
    if overrides is not None:
        authored = ConditionOverrides.model_validate_json(overrides.read_text(encoding="utf-8"))
        for identity, body in authored.conditions.items():
            recipe = recipes[identity]
            persistent = recipe.persistent.model_copy(update={"bodyPose": body.bodyPose, "label": body.label})
            recipes[identity] = ConditionRecipe.model_validate({
                **recipe.model_dump(), "persistent": persistent,
                "application": recipe.application.model_copy(update={"bodyAnimation": body.applicationBody}),
                "removal": recipe.removal.model_copy(update={"bodyAnimation": body.removalBody}),
            })
    return MappingProxyType(recipes)
