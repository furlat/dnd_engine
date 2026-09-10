"""Passive Python records for the imported NeuroStudio authoring format.

Names and optional fields follow spellAuthoring/types.ts. Missing optional data
stays missing; the offline TypeScript materializer owns authored defaults.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Annotated, Literal, Mapping, TypeVar

from pydantic import (
    AfterValidator, BaseModel, ConfigDict, Field, JsonValue, PlainSerializer,
    model_validator,
)

from dnd.core.content.identities import ContentRef
from game.condition_types import ConditionRecipe

T = TypeVar("T")
FrozenMap = Annotated[
    Mapping[str, T], AfterValidator(MappingProxyType),
    PlainSerializer(dict, return_type=dict),
]
Facing8 = Literal["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
FacingMap = Annotated[
    Mapping[Facing8, T], AfterValidator(MappingProxyType),
    PlainSerializer(dict, return_type=dict),
]
DepthMode = Literal["overlay", "world", "ground"]
BlendMode = Literal["normal", "add", "screen"]
Positive = Annotated[float, Field(gt=0)]
NonNegative = Annotated[float, Field(ge=0)]
Color = Annotated[int, Field(ge=0, le=0xFFFFFF)]
Identifier = Annotated[str, Field(min_length=1)]
BodySpeed = Annotated[float, Field(ge=0.1, le=4)]
BodyFrame = Annotated[int, Field(ge=0, le=14)]


@dataclass(frozen=True, slots=True)
class RigLayer:
    """Resolved actor appearance independent of media and mechanical owners."""

    slot: str
    category: str
    tint: int = 0xFFFFFF
    alpha: float = 1.0


class AuthoredRecord(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", frozen=True, allow_inf_nan=False)


class ElementColors(AuthoredRecord):
    primary: Color
    secondary: Color
    tertiary: Color


class LayerColors(AuthoredRecord):
    source: Literal["auto", "override"]
    primary: Color
    secondary: Color | None = None
    tertiary: Color | None = None
    mode: Literal["tint", "multiTint", "paletteSwap", "shaderUniform"]


class StudioActorLayer(AuthoredRecord):
    id: Identifier
    slot: Literal["weaponGlow", "aura", "effect", "effect2", "effect3", "slash"]
    enabled: bool
    hidden: bool
    category: Identifier
    colors: LayerColors


class StudioEquipment(AuthoredRecord):
    kind: Literal["unchanged", "hidden", "melee", "ranged"]


class StudioRecovery(AuthoredRecord):
    enabled: bool
    bodyClip: Literal["Taunt", "Special1", "Rolling"]
    bodyPlaybackSpeed: BodySpeed


class StudioCast(AuthoredRecord):
    actionClip: Literal["Attack1", "Attack2", "Attack3", "Attack4", "Attack5", "Attack6", "Special1"]
    bodyPlaybackSpeed: BodySpeed | None = None
    releaseFrame: BodyFrame
    equipment: StudioEquipment | None = None
    weaponGlow: StudioActorLayer | None = None
    aura: StudioActorLayer | None = None
    effects: tuple[StudioActorLayer, ...] | None = None
    slash: StudioActorLayer | None = None
    recovery: StudioRecovery

    @model_validator(mode="after")
    def validate_layer_slots(self) -> StudioCast:
        for slot, layer in (("weaponGlow", self.weaponGlow), ("aura", self.aura), ("slash", self.slash)):
            if layer is not None and layer.slot != slot:
                raise ValueError(f"cast.{slot}.slot must be {slot}")
        if self.effects is not None and any(layer.slot not in {"effect", "effect2", "effect3"} for layer in self.effects):
            raise ValueError("cast.effects must use effect, effect2 or effect3 slots")
        return self


class StudioCondition(AuthoredRecord):
    anchor: Literal["effect"]
    delayMs: NonNegative
    feedbackEnabled: bool


class StudioProjectilePhase(AuthoredRecord):
    enabled: bool
    assetId: Identifier | None = None
    assetPhase: Literal["cast", "travel", "impact"]
    startFrame: BodyFrame | None = None
    fps: Positive | None = None
    durationMs: Positive | None = None


class Point(AuthoredRecord):
    x: float
    y: float


class PaletteSwap(AuthoredRecord):
    originalColors: Annotated[tuple[Color, ...], Field(min_length=1, max_length=8)]
    targetColors: Annotated[tuple[Color, ...], Field(min_length=1, max_length=8)]
    tolerance: Annotated[float, Field(ge=0, le=1)]

    @model_validator(mode="after")
    def validate_color_count(self) -> PaletteSwap:
        if len(self.originalColors) != len(self.targetColors):
            raise ValueError("paletteSwap color rows must have equal length")
        return self


class ProjectileGeometry(AuthoredRecord):
    renderer: Literal["geometry_projectile"]
    enabled: bool
    primitive: Literal["bolt", "ray", "orb", "beam", "dart", "spray", "radiance", "rain"]


class ProjectileSprite(AuthoredRecord):
    renderer: Literal["sprite_projectile"]
    assetId: Identifier
    alpha: Annotated[float, Field(ge=0, le=1)]
    tint: Color
    blendMode: BlendMode
    offsetX: float
    offsetY: float
    anchor: Point | None = None
    paletteSwap: PaletteSwap | None = None
    geometryComposition: Literal["replace_geometry", "overlay_geometry"]
    mediaFailurePolicy: Literal["omit_optional_track", "fail_transaction"]


class StraightTrajectory(AuthoredRecord):
    type: Literal["straight"]
    sameTargetSpread: bool


class BezierTrajectory(AuthoredRecord):
    type: Literal["bezier"]
    curvature: float
    sameTargetSpread: bool


class ProjectileOrientation(AuthoredRecord):
    rowSource: Literal["targetVector"]
    fineRotation: Literal["none", "isometricHybrid"]
    directionSource: Literal["target_vector", "tangent", "locked_initial_tangent"]
    rotationOffsetDeg: float


class TargetAnchor(AuthoredRecord):
    basis: Literal["tileCenter"]
    liftY: float
    forwardPx: float


class SourceAnchor(TargetAnchor):
    sidePx: float
    axisPx: float


class StudioProjectile(AuthoredRecord):
    geometry: ProjectileGeometry
    sprite: ProjectileSprite | None
    prepare: StudioProjectilePhase
    travel: StudioProjectilePhase
    impact: StudioProjectilePhase
    trajectory: Annotated[StraightTrajectory | BezierTrajectory, Field(discriminator="type")]
    speedPxPerSecond: Positive
    minimumTravelDurationMs: Positive
    fps: Positive
    scale: Positive
    depthMode: DepthMode
    orientation: ProjectileOrientation
    sourceAnchor: SourceAnchor
    targetAnchor: TargetAnchor
    sourceAnchorsByFacing: FacingMap[SourceAnchor] | None = None
    missileStaggerMs: NonNegative
    colors: LayerColors | None = None

    @model_validator(mode="after")
    def validate_phase_names(self) -> StudioProjectile:
        for field, expected, phase in (("prepare", "cast", self.prepare), ("travel", "travel", self.travel), ("impact", "impact", self.impact)):
            if phase.assetPhase != expected:
                raise ValueError(f"projectile.{field}.assetPhase must be {expected}")
        if not self.geometry.enabled and self.sprite is None:
            raise ValueError("projectile must enable geometry, sprite media or both")
        if self.sprite is not None and self.sprite.geometryComposition == "overlay_geometry" and not self.geometry.enabled:
            raise ValueError("projectile overlay_geometry requires enabled geometry")
        return self


class AreaShapePhase(AuthoredRecord):
    enabled: Literal[True]
    durationMs: NonNegative
    effectProgress: Annotated[float, Field(ge=0, le=1)]


class AreaExplosionPhase(AuthoredRecord):
    enabled: bool
    durationMs: NonNegative
    effectProgress: Annotated[float, Field(ge=0, le=1)]
    startScale: NonNegative
    endScale: NonNegative
    fillAlphaEnd: float
    strokeAlphaEnd: float


class AreaPhases(AuthoredRecord):
    shape: AreaShapePhase
    explosion: AreaExplosionPhase


class AreaGeometry(AuthoredRecord):
    renderer: Literal["geometry_area"]
    enabled: bool
    depthMode: DepthMode
    startScale: NonNegative
    endScale: NonNegative
    fillAlphaStart: float
    fillAlphaEnd: float
    strokeAlphaStart: float
    strokeAlphaEnd: float
    strokeWidth: NonNegative


class AreaSpriteSource(AuthoredRecord):
    category: Identifier
    animation: Identifier


class AreaSprite(AuthoredRecord):
    renderer: Literal["strip_aoe"]
    source: AreaSpriteSource
    compatibleShapes: tuple[Literal["sphere", "cone", "line", "cube", "cylinder"], ...]
    fit: Literal["geometry_bounds"]
    fps: Positive
    durationMs: NonNegative | None = None
    effectFrame: NonNegative
    tintMode: Literal["element_primary", "original"]
    alpha: float
    blendMode: BlendMode
    depthMode: DepthMode
    geometryComposition: Literal["replace_geometry", "overlay_geometry"]
    mediaFailurePolicy: Literal["omit_optional_track", "fail_transaction"]


class StudioArea(AuthoredRecord):
    shapeSource: Literal["authoritative_cue"]
    phases: AreaPhases
    geometry: AreaGeometry
    sprite: AreaSprite | None


class HitFlash(AuthoredRecord):
    enabled: bool
    frame: BodyFrame
    durationMs: Positive
    color: Color


class FloatingNumber(AuthoredRecord):
    enabled: bool
    frame: BodyFrame
    durationMs: Positive
    label: str
    color: Color


class DamageDeath(AuthoredRecord):
    enabled: bool
    frame: BodyFrame


class StudioDamage(AuthoredRecord):
    impactDelayMs: NonNegative
    hitFlash: HitFlash
    floatingNumber: FloatingNumber
    death: DamageDeath | None = None


class StudioSpellDraft(AuthoredRecord):
    definitionRef: ContentRef
    elementColors: ElementColors
    cast: StudioCast
    projectile: StudioProjectile | None = None
    area: StudioArea | None = None
    damage: StudioDamage | None = None
    condition: StudioCondition | None = None


class StudioDraftFile(AuthoredRecord):
    schema_: Literal["neuroclient.spellStudioDrafts"] = Field(alias="schema")
    version: Literal[6]
    spells: tuple[StudioSpellDraft, ...]


class AuthoredProjectilePhase(AuthoredRecord):
    start: Annotated[int, Field(ge=0)]
    frames: Annotated[int, Field(ge=1)]
    fps: Positive | None = None
    loop: bool


class ProjectileFrame(AuthoredRecord):
    width: Annotated[int, Field(ge=1)]
    height: Annotated[int, Field(ge=1)]
    cols: Annotated[int, Field(ge=1)]
    rows: Literal[8]


class AuthoredProjectilePhases(AuthoredRecord):
    travel: AuthoredProjectilePhase
    cast: AuthoredProjectilePhase | None = None
    impact: AuthoredProjectilePhase | None = None


class PalettePreview(AuthoredRecord):
    colors: Annotated[tuple[Color, ...], Field(min_length=1)]
    palette: str | None = None


class ProjectileSource(AuthoredRecord):
    package: str | None = None
    manifest: str | None = None
    asset: str | None = None
    mode: str | None = None
    sourceSheet: str | None = None
    sourceMatrix: str | None = None
    chosenImpact: str | None = None
    palette: str | None = None
    notes: str | None = None


class ProjectileValidation(AuthoredRecord):
    emptyCells: int | None = None
    edgeContacts: int | None = None
    warnings: tuple[str, ...] | None = None


class ProjectileAssetAnchor(AuthoredRecord):
    x: Annotated[float, Field(ge=0, le=1)]
    y: Annotated[float, Field(ge=0, le=1)]


class AuthoredProjectileAsset(AuthoredRecord):
    assetId: Identifier
    displayName: str
    kind: Literal["projectile"]
    sheet: Identifier
    preview: str | None = None
    frame: ProjectileFrame
    fps: Positive
    rowOrder: tuple[Facing8, ...]
    phases: AuthoredProjectilePhases
    anchor: ProjectileAssetAnchor
    defaultScale: Positive
    tags: tuple[str, ...] | None = None
    palettePreview: PalettePreview
    source: ProjectileSource | None = None
    validation: ProjectileValidation | None = None


class RigTables(AuthoredRecord):
    FACING_ROW: FacingMap[int]
    FACING_CYCLE: tuple[Facing8, ...]
    SHEET_COLS: Annotated[int, Field(ge=1)]
    CELL_W: Annotated[int, Field(ge=1)]
    CELL_H: Annotated[int, Field(ge=1)]
    ANIM_FPS: Positive
    SLOT_RENDER_ORDER: tuple[str, ...]
    SLOT_CATEGORIES: FrozenMap[tuple[str, ...]]
    HAIR_CATEGORIES: tuple[str, ...]
    AUTHORED_PROJECTILE_ROW_ORDER: tuple[Facing8, ...]
    RIG_ORIGIN_Y_FROM_GROUND: float
    TILE_W: Positive
    TILE_H: Positive


class BodyClip(AuthoredRecord):
    """One semantic body clip resolved to exact local sheet bindings."""

    source_clip: Identifier
    frames: Annotated[int, Field(ge=1)]
    fps: Positive
    sheets: FrozenMap[str]


class BodyRig(AuthoredRecord):
    """Passive body layout/capabilities, shared by timing and pixel sampling."""

    cell_width: Annotated[int, Field(ge=1)]
    cell_height: Annotated[int, Field(ge=1)]
    origin_y_from_ground: float
    facing_rows: FacingMap[int]
    slot_order: tuple[str, ...]
    slot_categories: FrozenMap[tuple[str, ...]]
    clips: FrozenMap[BodyClip]

    @model_validator(mode="after")
    def validate_layout(self) -> BodyRig:
        facings = {"N", "NE", "E", "SE", "S", "SW", "W", "NW"}
        if set(self.facing_rows) != facings or set(self.facing_rows.values()) != set(range(8)):
            raise ValueError("body rig requires eight distinct facing rows 0..7")
        if (len(set(self.slot_order)) != len(self.slot_order)
                or set(self.slot_order) != set(self.slot_categories)
                or "body" not in self.slot_order):
            raise ValueError("body rig requires a body and unique declared slots in render order")
        for slot, categories in self.slot_categories.items():
            if not slot or not categories or any(not category for category in categories) or len(set(categories)) != len(categories):
                raise ValueError("body rig slot categories must be nonempty and unique")
        categories = {category for values in self.slot_categories.values() for category in values}
        if not self.clips or any(not clip for clip in self.clips):
            raise ValueError("body rig requires named clip bindings")
        for clip in self.clips.values():
            if not clip.sheets or not set(clip.sheets) <= categories:
                raise ValueError("body clip sheets must use declared rig categories")
        return self


class DamagePaletteEntry(AuthoredRecord):
    label: str | None = None
    elementColors: ElementColors
    impactColor: Color


class DamagePalette(AuthoredRecord):
    untyped: DamagePaletteEntry
    byDamageType: FrozenMap[DamagePaletteEntry]


class DamageContext(AuthoredRecord):
    palette: DamagePalette
    bodyClip: Identifier
    bodyPlaybackSpeed: Positive
    impactDelayMs: NonNegative
    flashEnabled: bool
    flashFrame: NonNegative
    flashColorMode: Literal["damage_type", "fixed"]
    flashColor: Color
    criticalFlashColor: Color
    flashDurationMs: NonNegative
    numberEnabled: bool
    numberFrame: NonNegative
    numberDurationMs: NonNegative
    conditionFrame: NonNegative
    deathFrame: NonNegative


class DeathContext(AuthoredRecord):
    bodyClip: Identifier
    bodyPlaybackSpeed: Positive
    equipmentHideFrame: NonNegative
    hiddenSlots: tuple[str, ...]
    media: tuple[JsonValue, ...]


class EquipmentTransitionContext(AuthoredRecord):
    bodyEnabled: bool
    bodyClip: Literal["Taunt", "Special1", "Rolling"]
    bodyPlaybackSpeed: BodySpeed
    commitFrame: Annotated[int, Field(ge=0, le=120)]
    media: tuple[JsonValue, ...]


class MovementMediaTrack(AuthoredRecord):
    id: Identifier
    role: Literal["source_vfx", "takeoff", "trail", "landing", "impact", "particles", "transition", "recovery"]
    assetId: Identifier
    attachment: Literal["body", "ground"]
    tint: Color
    tint2: Color | None
    startFrame: Annotated[int, Field(ge=0, le=120)]
    fps: Annotated[float, Field(ge=1, le=120)]
    loop: bool
    reversed: bool
    scale: Annotated[float, Field(ge=0.1, le=8)]
    offsetX: Annotated[float, Field(ge=-512, le=512)]
    offsetY: Annotated[float, Field(ge=-512, le=512)]


class MovementRecovery(AuthoredRecord):
    enabled: bool
    bodyClip: Literal["Taunt", "Special1", "Rolling"]
    bodyPlaybackSpeed: BodySpeed
    media: tuple[MovementMediaTrack, ...]


class MovementReactionContext(AuthoredRecord):
    label: str
    feedbackEnabled: bool
    feedbackColor: Color
    movementLeadInMs: NonNegative
    bodyEnabled: bool
    bodyClip: Literal["Taunt", "Special1", "Rolling"]
    bodyPlaybackSpeed: BodySpeed
    media: tuple[MovementMediaTrack, ...]
    recovery: MovementRecovery


class VoluntaryMovementContext(AuthoredRecord):
    walkClip: Literal["Run", "Walk"]
    walkPlaybackSpeed: Annotated[float, Field(ge=0.1, le=8)]
    walkStepDurationMs: Annotated[float, Field(ge=80, le=2000)]
    walkMedia: tuple[MovementMediaTrack, ...]
    walkRecovery: MovementRecovery
    jumpClip: Literal["Rolling", "AttackRun", "AttackRun2"]
    jumpBodyFrames: Annotated[int, Field(ge=1, le=120)]
    jumpSourceFps: Annotated[float, Field(ge=1, le=120)]
    jumpBaseDurationMs: Annotated[float, Field(ge=100, le=2000)]
    jumpPerCellDurationMs: Annotated[float, Field(ge=0, le=500)]
    jumpMinDurationMs: Annotated[float, Field(ge=100, le=2000)]
    jumpMaxDurationMs: Annotated[float, Field(ge=100, le=3000)]
    jumpArcBasePx: Annotated[float, Field(ge=0, le=200)]
    jumpArcPerCellPx: Annotated[float, Field(ge=0, le=100)]
    jumpArcMaxPx: Annotated[float, Field(ge=0, le=300)]
    jumpMedia: tuple[MovementMediaTrack, ...]
    jumpRecovery: MovementRecovery

    @model_validator(mode="after")
    def validate_jump_duration(self) -> VoluntaryMovementContext:
        if self.jumpMinDurationMs > self.jumpMaxDurationMs:
            raise ValueError("jumpMinDurationMs must not exceed jumpMaxDurationMs")
        return self


class FloatingFeedbackStyle(AuthoredRecord):
    fontFamily: str
    fontSizePx: Positive
    fontWeight: str
    strokeColor: Color
    strokeWidthPx: NonNegative
    anchorLiftPx: float
    risePx: float
    fadeStartFraction: Annotated[float, Field(ge=0, le=1)]
    durationMs: Positive


class DartStyle(AuthoredRecord):
    """The existing generated profile's geometry dart drawing values."""

    trailPointLimit: Annotated[int, Field(ge=1)]
    trailWidthPx: Positive
    trailAlpha: Annotated[float, Field(gt=0, le=1)]
    headRadiusPx: Positive
    headAlpha: Annotated[float, Field(gt=0, le=1)]


class BoltStyle(AuthoredRecord):
    maximumLengthPx: Positive
    distanceLengthRatio: Positive
    strokeWidthPx: Positive
    strokeAlpha: Annotated[float, Field(gt=0, le=1)]
    headRadiusPx: Positive
    headAlpha: Annotated[float, Field(gt=0, le=1)]


class ActionActor(AuthoredRecord):
    enabled: bool
    clip: Identifier
    playbackSpeed: Positive
    hiddenSlots: tuple[str, ...]
    media: tuple[JsonValue, ...]


class ActionFrameAnchor(AuthoredRecord):
    name: Identifier
    frame: BodyFrame


class AttackProfileMatch(AuthoredRecord):
    kind: Literal["attack"]
    delivery: Literal["melee", "projectile"] | None
    weaponSlots: tuple[str, ...] | None
    outcomes: tuple[str, ...] | None
    primaryDamageTypes: tuple[str, ...] | None
    elemental: bool | None
    sourceItemRefs: tuple[ContentRef, ...] | None


class AttackVfxLayer(AuthoredRecord):
    category: Identifier
    tint: Color | Literal["white", "$element", "$element.primary", "$element.secondary", "$element.tertiary"]


class AttackVfx(AuthoredRecord):
    onHit: FrozenMap[AttackVfxLayer]
    onMiss: FrozenMap[AttackVfxLayer]
    onCrit: FrozenMap[AttackVfxLayer] | None = None


class ActionProjectile(AuthoredRecord):
    """Original action projectile profile; distinct from a Studio spell draft."""

    geometry: ProjectileGeometry
    speedPxPerSecond: Positive
    minimumTravelDurationMs: Positive
    trajectory: Annotated[StraightTrajectory | BezierTrajectory, Field(discriminator="type")]
    originX: float
    originY: float
    sourceForwardPx: float
    targetY: float
    targetForwardPx: float
    depthMode: DepthMode
    debugAnchor: bool


class AttackVariant(AuthoredRecord):
    id: Identifier
    precedence: int
    match: AttackProfileMatch
    actor: ActionActor
    anchors: tuple[ActionFrameAnchor, ...]
    attackVfx: AttackVfx
    projectile: ActionProjectile | None


class ActionFeedback(AuthoredRecord):
    text: Identifier
    color: Color


class AttackRecipe(AuthoredRecord):
    """Existing contentActionPresentationRecipes attack rows, without defaults."""

    definitionRef: ContentRef
    compatibleCueKinds: tuple[str, ...]
    previewChildCueKinds: tuple[str, ...]
    disposition: Literal["authored"]
    mediaFailurePolicy: Literal["fail_transaction", "omit_optional_track"]
    actor: ActionActor
    anchors: tuple[ActionFrameAnchor, ...]
    attackFeedback: FrozenMap[ActionFeedback | None]
    counterspellFeedback: JsonValue
    variants: tuple[AttackVariant, ...]
    projectile: JsonValue
    actionFeedback: JsonValue


@dataclass(frozen=True, slots=True)
class AnimationData:
    drafts: Mapping[str, StudioSpellDraft]
    attack_recipes: Mapping[str, AttackRecipe]
    condition_recipes: Mapping[str, ConditionRecipe]
    projectile_assets: Mapping[str, AuthoredProjectileAsset]
    rig: RigTables
    resources: Mapping[str, Path]
    root_rig: str
    rigs: Mapping[str, BodyRig]
    creature_rigs: Mapping[str, str]
    damage_context: DamageContext
    death_context: DeathContext
    equipment_context: EquipmentTransitionContext
    movement_context: VoluntaryMovementContext
    movement_reaction_context: MovementReactionContext
    number_style: FloatingFeedbackStyle
    badge_style: FloatingFeedbackStyle
    dart_style: DartStyle
    bolt_style: BoltStyle
    vfx_source_hues: Mapping[str, float]
    # Unused action contexts remain exact source JSON until their family is ported.
    context_source_json: str
