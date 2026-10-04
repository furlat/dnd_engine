"""Passive Python records for the imported NeuroStudio authoring format.

Names and optional fields follow spellAuthoring/types.ts, with explicit local
extensions documented in data/PRESENTATION_CONTRACT.md. The imported baseline
retains its materialized defaults; local recipes own their authored values.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Annotated, Literal, Mapping, TypeVar
from uuid import UUID

from pydantic import (
    AfterValidator, BaseModel, ConfigDict, Field, JsonValue, PlainSerializer,
    field_serializer, field_validator, model_validator,
)

from dnd.core.content.identities import ContentRef
from dnd.types.event_facts import MovementTrajectory
from dnd.types.world import MovementMode
from dnd.types.summoning import SummonManifestation
from dnd.core.condition_types import ConditionTag
from dnd.core.item_types import ItemEffectPresentationState
from dnd.core.life_types import LifeState
from dnd.core.creature_types import DamageType
from dnd.types.class_features import DraconicPresenceMode
from game.condition_types import ConditionBodyAnimation, ConditionRecipe, ConditionBodyRamp, ConditionLayer
from game.condition_media import ConditionLayerMedia
from game.device_art import DeviceArt
from game.portal_art import PortalArt, DoorwayArt

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
    item_effects: tuple[ItemEffectPresentationState, ...] = ()
    item_uuid: UUID | None = None
    suppression_provider_uuids: tuple[UUID, ...] = ()


@dataclass(frozen=True, slots=True)
class ItemAttachmentStart:
    """Witnessed application time retained independently of item exposure."""

    item_uuid: UUID
    applied_ms: float | None = None
    source_cursor: int | None = None


class AuthoredRecord(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", frozen=True, allow_inf_nan=False)


class ElementColors(AuthoredRecord):
    primary: Color
    secondary: Color
    tertiary: Color


class LayerColors(AuthoredRecord):
    source: Literal["auto", "override"] = "auto"
    primary: Color
    secondary: Color | None = None
    tertiary: Color | None = None
    mode: Literal["tint", "multiTint", "paletteSwap", "shaderUniform"]


class PaletteTreatment(AuthoredRecord):
    """Exact authored colors and optional source noise for isolated recoloring."""

    colors: Annotated[tuple[Color, ...], Field(min_length=1)]
    gamma: Positive = .65
    noiseSheet: Identifier | None = None
    untinted: bool = False


class BodyMaterial(AuthoredRecord):
    """A retained manifestation selects palette replacement and body opacity."""

    palette: ConditionBodyRamp
    alpha: Annotated[float, Field(ge=0, le=1)]


class StudioActorLayer(AuthoredRecord):
    id: Identifier
    slot: Literal["weaponGlow", "aura", "effect", "effect2", "effect3", "slash"]
    enabled: bool
    hidden: bool
    category: Identifier
    colors: LayerColors
    # Optional isolated export; automatic palettes replace only its effect pixels.
    sourceSheet: Identifier | None = None
    # Override: offline bake metadata. Auto: resolved from the owning spell at bind time.
    palette: PaletteTreatment | None = None
    blendMode: BlendMode = "normal"


class StudioEquipment(AuthoredRecord):
    kind: Literal["unchanged", "hidden", "melee", "ranged"]


class ChildAttackPose(AuthoredRecord):
    """Layers fitted to a rig/clip, optionally restricted to one weapon category."""

    rigId: Identifier
    weaponCategory: Identifier | None = None
    clip: Identifier
    layers: Annotated[tuple[StudioActorLayer, ...], Field(min_length=1)]


class ChildAttackPresentation(AuthoredRecord):
    """The actual child weapon attack owns this spell's body and delivery."""

    poses: Annotated[tuple[ChildAttackPose, ...], Field(min_length=1)]


class StudioRecovery(AuthoredRecord):
    enabled: bool
    bodyClip: Literal["Taunt", "Special1", "Rolling"]
    bodyPlaybackSpeed: BodySpeed


class StudioCast(AuthoredRecord):
    enabled: bool = True
    actionClip: Literal["Attack1", "Attack2", "Attack3", "Attack4", "Attack5", "Attack6", "Special1"]
    bodyPlaybackSpeed: BodySpeed | None = None
    releaseFrame: BodyFrame
    equipment: StudioEquipment | None = None
    weaponGlow: StudioActorLayer | None = None
    aura: StudioActorLayer | None = None
    effects: tuple[StudioActorLayer, ...] | None = None
    slash: StudioActorLayer | None = None
    recovery: StudioRecovery
    holdReleaseForVolley: bool = False
    holdUntilContact: bool = False
    sourceSockets: SourceSockets | None = None

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


class MediaTimePoint(AuthoredRecord):
    elapsedMs: NonNegative
    sourceFrame: NonNegative


class StudioProjectilePhase(AuthoredRecord):
    enabled: bool
    onMiss: Literal["play", "omit"] = "play"
    assetId: Identifier | None = None
    assetPhase: Literal["cast", "travel", "impact"]
    startFrame: BodyFrame | None = None
    fps: Positive | None = None
    durationMs: Positive | None = None
    fitDuration: bool = False
    overlapRelease: bool = False
    scale: Positive | None = None
    fineRotation: Literal["none", "isometricHybrid"] | None = None
    viewFacing: Facing8 | None = None
    timeMap: tuple[MediaTimePoint, ...] = ()
    overlapContactMs: NonNegative = 0
    composition: Literal["billboard", "xyz_volume"] = "billboard"
    supportClipping: Literal["physical", "raised"] = "physical"


class TargetLocalDelivery(AuthoredRecord):
    """A target-local visual can begin before its mechanical contact anchor."""

    contactAfterReleaseMs: NonNegative = 0
    approachOffsetTiles: NonNegative = 0
    approachUntilFrame: NonNegative = 0


class Point(AuthoredRecord):
    x: float
    y: float


class SourceSockets(AuthoredRecord):
    """Measured pixels in the actor's source sheet, before rig/camera scale."""

    release: FacingMap[Point]
    preparation: FacingMap[tuple[Point | None, ...]] | None = None


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
    basis: Literal["tileCenter", "rigRoot", "body"]
    liftY: float
    forwardPx: float
    axisPx: float = 0


class SourceAnchor(AuthoredRecord):
    basis: Literal["tileCenter", "rigRoot", "body"]
    liftY: float
    forwardPx: float
    sidePx: float
    axisPx: float


class StudioProjectile(AuthoredRecord):
    requireAttackOutcome: bool = False
    targetLocal: TargetLocalDelivery | None = None
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
    sourceSockets: SourceSockets | None = None
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


class SurfaceReveal(AuthoredRecord):
    """Reveal recorded residue changes outward from an area's ground contact."""

    residueIds: Annotated[tuple[Identifier, ...], Field(min_length=1)]
    speedTilesPerSecond: Positive


class StudioArea(AuthoredRecord):
    shapeSource: Literal["authoritative_cue"]
    phases: AreaPhases
    geometry: AreaGeometry
    sprite: AreaSprite | None
    surfaceReveal: SurfaceReveal | None = None


class HitFlash(AuthoredRecord):
    enabled: bool
    frame: BodyFrame
    durationMs: Positive
    color: Annotated[int, Field(ge=0, le=0xFFFFFF)]
    palette: PaletteTreatment | None = None


class FloatingNumber(AuthoredRecord):
    enabled: bool
    frame: BodyFrame
    durationMs: Positive
    label: str
    color: Annotated[int, Field(ge=0, le=0xFFFFFF)]


class DamageDeath(AuthoredRecord):
    enabled: bool
    frame: BodyFrame


class StudioDamage(AuthoredRecord):
    impactDelayMs: NonNegative
    hitFlash: HitFlash
    floatingNumber: FloatingNumber
    death: DamageDeath | None = None


class ApplicationOutcome(AuthoredRecord):
    """Authored selectors over one committed application, never inferred mechanics."""

    requireRemovedConditionTag: ConditionTag | None = None
    requiredSaveSuccess: bool | None = None
    requireAppliedConditionId: Identifier | None = None
    requiredLifeState: LifeState | None = None
    requireDamageApplied: bool = False
    rigIds: tuple[Identifier, ...] = ()


class BodyMaterialPoint(AuthoredRecord):
    elapsedMs: NonNegative
    strength: Annotated[float, Field(ge=0, le=1)]
    pulse: Annotated[float, Field(ge=0, le=1)] = 0


class RisingMotes(AuthoredRecord):
    """Original deterministic world particles around an observed owner."""
    blendMode: Literal["normal", "screen"] = "normal"
    count: Annotated[int, Field(ge=1)]
    radiusCells: NonNegative
    radialGrowthCells: NonNegative = 0
    heightCells: Positive
    depthRatio: Positive = 1
    periodMs: Positive = 2000
    palette: tuple[int, int]
    brightEvery: Annotated[int, Field(ge=1)]
    alpha: Annotated[float, Field(ge=0, le=1)]
    sizePixels: tuple[Positive, Positive]
    formationOnlyMs: Positive | None = None


class ObjectIntake(AuthoredRecord):
    """Finite serving particles from the selected object to the current pose socket."""
    blendMode: Literal["normal", "screen"] = "normal"
    socket: Identifier
    sourceOffsetCells: tuple[float, float, float]
    count: Annotated[int, Field(ge=1)]
    delayPerParticle: NonNegative
    arcHeightCells: NonNegative
    palette: tuple[int, int]
    brightEvery: Annotated[int, Field(ge=1)]
    radiusPixels: tuple[Positive, Positive]
    alpha: Annotated[float, Field(ge=0, le=1)]


class StudioBodyMaterialTrack(ApplicationOutcome):
    """Finite current-silhouette material on a cast release or recipient contact."""

    id: Identifier
    material: ConditionBodyRamp
    clock: Literal["release", "contact"] = "release"
    motes: RisingMotes | None = None
    startOffsetMs: float = 0
    points: Annotated[tuple[BodyMaterialPoint, ...], Field(min_length=2)]

    @model_validator(mode="after")
    def finite_envelope(self) -> StudioBodyMaterialTrack:
        if self.points[0].elapsedMs != 0 or any(a.elapsedMs >= b.elapsedMs for a, b in zip(self.points, self.points[1:])):
            raise ValueError("material points must start at zero and increase strictly")
        if any(point.strength or point.pulse for point in (self.points[0], self.points[-1])):
            raise ValueError("finite body material must start and end clear")
        return self


@dataclass(frozen=True, slots=True)
class BodyMaterialSample:
    material: ConditionBodyRamp
    strength: float
    pulse: float = 0
    age_ms: float = 0


class StudioMediaTrack(ApplicationOutcome):
    """Finite authored media on the cast clock, independent of travel geometry."""

    id: Identifier
    assetId: Identifier
    assetIdsByCamera: tuple[Identifier, Identifier, Identifier, Identifier] | None = None
    poseSocket: Identifier | None = None
    whenPresenceMode: DraconicPresenceMode | None = None
    composition: Literal["billboard", "xyz_volume", "clump"] = "billboard"
    supportClipping: Literal["physical", "raised"] = "physical"
    blendMode: Literal["normal", "screen"] = "normal"
    assetPhase: Literal["cast", "travel", "impact"] = "impact"
    clock: Literal["release", "contact"] = "release"
    attachment: Literal["source_hand", "source_ground", "target_body", "target_ground", "area_ground",
                        "departure_ground", "arrival_ground"]
    startOffsetMs: float = 0
    fps: Positive | None = None
    durationMs: Positive | None = None
    loop: bool = False
    scale: Positive = 1
    scaleWithActor: bool = False
    alpha: Annotated[float, Field(ge=0, le=1)] = 1
    fadeInMs: NonNegative = 0
    fadeOutMs: NonNegative = 0
    fadeCurve: Literal["linear", "smoothstep"] = "linear"
    bodyOffsetsClip: str | None = None
    depth: Literal["world", "ground", "behind_body", "front_body"] = "world"
    orientation: Literal["authored", "target_vector"] = "authored"
    # Fixed-world orbit banks use an authored camera basis. Omission retains
    # facing-driven media such as directed projectiles and sprays.
    viewFacing: Facing8 | None = None
    onMiss: Literal["play", "omit"] = "play"
    actorTopClearancePx: NonNegative | None = None
    worldOffsetsByFacing: FacingMap[Point] | None = None
    # Camera-ground X+Z of a pre-rendered depth band, relative to its owner.
    # Changes painter order only; registration and gameplay extent stay fixed.
    sortDepthByFacing: FacingMap[float] | None = None
    timeMap: tuple[MediaTimePoint, ...] = ()
    timeMapsByFacing: FacingMap[tuple[MediaTimePoint, ...]] | None = None
    bodyOffsetsByFacing: FacingMap[tuple[Point, ...]] | None = None
    # Source pixels from whole-effect origin to the baked attachment point.
    emissionPointByFacing: FacingMap[Point] | None = None

    @model_validator(mode="after")
    def removal_gate_target(self) -> StudioMediaTrack:
        if self.clock == "contact" and not self.attachment.startswith("target_"):
            raise ValueError("contact media requires a recorded recipient attachment")
        if self.requireRemovedConditionTag is not None and not self.attachment.startswith("target_"):
            raise ValueError("condition-removal media requires a target attachment")
        if self.requiredSaveSuccess is not None and not self.attachment.startswith("target_"):
            raise ValueError("save-outcome media requires a target attachment")
        if (self.requireAppliedConditionId is not None or self.requiredLifeState is not None or self.requireDamageApplied) and not self.attachment.startswith("target_"):
            raise ValueError("application-outcome media requires a target attachment")
        if self.actorTopClearancePx is not None and not self.attachment.startswith("target_"):
            raise ValueError("actor clearance requires a target attachment")
        return self


class BodyActionMediaTrack(StudioMediaTrack):
    """The same finite source sampler, selected by an actor action's own outcome."""

    requireHealingApplied: bool = False

    @model_validator(mode="after")
    def removal_gate_target(self) -> BodyActionMediaTrack:
        if self.clock != 'release' or self.attachment not in ('source_ground','source_hand'):
            raise ValueError('Body action media requires its actor release attachment')
        if (self.requireRemovedConditionTag is not None or self.requiredLifeState is not None
                or self.requireDamageApplied or self.actorTopClearancePx is not None):
            raise ValueError('Body action media cannot select a spell recipient outcome')
        return self


class StudioContact(AuthoredRecord):
    """Presentation arrival; outcomes still come solely from native events."""

    delayMs: NonNegative = 0
    launchDelayMs: NonNegative = 0
    speedTilesPerSecond: Positive | None = None
    cellsByFacing: FacingMap[FrozenMap[NonNegative]] | None = None

    @field_serializer("cellsByFacing")
    def serialize_cell_contacts(self, value: Mapping[Facing8, Mapping[str, float]] | None
                                ) -> dict[Facing8, dict[str, float]] | None:
        return None if value is None else {facing: dict(cells) for facing, cells in value.items()}


class StudioArcDelivery(AuthoredRecord):
    """Accepted textured ribbons on resolved edges or the native line corridor."""
    texture: str
    glow: str
    star: str
    streak: str
    spark: str
    mode: Literal["applications", "area_line", "ground_strike"]
    coreCount: Annotated[int, Field(ge=1, le=8)] = 1
    widthCells: Positive
    secondaryWidthCells: Positive
    travelBaseMs: NonNegative
    travelPerCellMs: NonNegative
    maximumTravelMs: Positive
    branchDelayMs: NonNegative = 0
    chargeStartMs: NonNegative = 180
    decayStartMs: NonNegative = 240
    decayEndMs: Positive = 760
    contactDecayStartMs: NonNegative = 320
    contactDecayEndMs: Positive = 1120

    @model_validator(mode="after")
    def finite_decay(self) -> StudioArcDelivery:
        if self.decayEndMs <= self.decayStartMs or self.contactDecayEndMs <= self.contactDecayStartMs:
            raise ValueError("arc decay ends must follow their starts")
        return self


class StudioDirectedEye(AuthoredRecord):
    sizeCells: tuple[Positive, Positive]
    replaceLayerIds: tuple[str, ...]


class StudioNoiseRibbonDelivery(AuthoredRecord):
    """Original procedural material over actual source/recipient geometry."""
    material: Literal["noise_ribbon"]
    verticalScale: Positive
    sourceEye: StudioDirectedEye | None = None
    texture: str
    palette: Annotated[tuple[Color, ...], Field(min_length=2)]
    sourceSocket: Literal["owner", "face", "hand"]
    sourcePlaneHeightCells: Positive
    targetPlaneHeightCells: Positive
    widthCells: Positive
    arcHeightCells: NonNegative
    contactFadeMs: NonNegative


class StudioDarknessMeshDelivery(AuthoredRecord):
    """Original donor mesh resources and evaluated owner-local launch socket."""
    material: Literal["darkness_mesh"]
    geometry: str
    palette: Annotated[tuple[Color, ...], Field(min_length=2)]
    nativeUnitsPerCell: Positive
    verticalScale: Positive
    sourceOffsetNativeXYZ: tuple[float, float, float]
    targetPlaneHeightCells: Positive
    contactFadeMs: NonNegative


class StudioPlasmaTrailDelivery(AuthoredRecord):
    """Original plasma material inputs, on the measured actor hand plane."""
    material: Literal["plasma_trail"]
    particles: str
    sphere: str
    trailTexture: str
    noiseTexture: str
    palette: Annotated[tuple[Color, ...], Field(min_length=2)]
    nativeUnitsPerCell: Positive
    verticalScale: Positive
    sourceSocket: Literal["hand"]
    sourcePlaneHeightCells: Positive
    targetPlaneHeightCells: Positive
    contactFadeMs: NonNegative


StudioDirectedDelivery = Annotated[
    StudioNoiseRibbonDelivery | StudioDarknessMeshDelivery | StudioPlasmaTrailDelivery,
    Field(discriminator="material"),
]


class StudioCancellationMedia(AuthoredRecord):
    """Finite source cleanup for one received interruption outcome."""
    outcomeCode: Identifier
    reactionId: Identifier
    cutoffOffsetMs: float
    media: tuple[StudioMediaTrack, ...]
    reactionOffsetsByFacing: FacingMap[tuple[float, float, float]]
    successByCamera: tuple[Identifier, Identifier, Identifier, Identifier]
    reactionScale: Positive

    @model_validator(mode="after")
    def source_cleanup_only(self) -> StudioCancellationMedia:
        if any(track.attachment != "source_ground" or track.clock != "release"
               or track.composition != "billboard" for track in self.media):
            raise ValueError("cancellation cleanup requires finite source-ground billboard media")
        if any(track.loop for track in self.media):
            raise ValueError("cancellation cleanup must end")
        return self


class StudioCastPalette(AuthoredRecord):
    """A cast variant selected from its own received application evidence."""
    whenEnergyType: DamageType
    conditionId: Identifier | None = None
    spatialContentId: Identifier | None = None
    colors: ElementColors

    @model_validator(mode="after")
    def one_owner(self) -> StudioCastPalette:
        if (self.conditionId is None) == (self.spatialContentId is None):
            raise ValueError("cast palette requires one condition or spatial owner")
        return self


class StudioSpellDraft(AuthoredRecord):
    definitionRef: ContentRef
    elementColors: ElementColors
    castPalettes: tuple[StudioCastPalette, ...] = ()
    cast: StudioCast
    projectile: StudioProjectile | None = None
    area: StudioArea | None = None
    damage: StudioDamage | None = None
    condition: StudioCondition | None = None
    media: tuple[StudioMediaTrack, ...] = ()
    bodyMaterials: tuple[StudioBodyMaterialTrack, ...] = ()
    arcs: StudioArcDelivery | None = None
    directed: StudioDirectedDelivery | None = None
    cancellationMedia: StudioCancellationMedia | None = None
    displacementLayers: tuple[ConditionLayer, ...] = ()
    contact: StudioContact | None = None
    childAttack: ChildAttackPresentation | None = None

    @model_validator(mode="after")
    def arc_source_contract(self) -> StudioSpellDraft:
        if sum(value is not None for value in (self.arcs, self.directed, self.projectile)) > 1:
            raise ValueError("one authored delivery owns a cast trajectory")
        if self.directed is not None and (self.contact is None or self.contact.speedTilesPerSecond is None):
            raise ValueError("directed material requires its authored contact speed")
        if self.arcs is not None:
            if self.cast.sourceSockets is None:
                raise ValueError("directed arc delivery requires authored cast sourceSockets")
            if self.projectile is not None:
                raise ValueError("directed arcs and projectile delivery cannot own the same cast")
        return self


class StudioDraftFile(AuthoredRecord):
    schema_: Literal["neuroclient.spellStudioDrafts", "dnd.spellStudioDrafts"] = Field(alias="schema")
    version: Literal[1, 2, 3, 6]
    spells: tuple[StudioSpellDraft, ...]
    effectDrafts: FrozenMap[StudioSpellDraft] = Field(default_factory=dict)

    @model_validator(mode="after")
    def format_version(self) -> StudioDraftFile:
        supported = (6,) if self.schema_ == "neuroclient.spellStudioDrafts" else (1, 2, 3)
        if self.version not in supported:
            raise ValueError(f"{self.schema_} requires version {supported}")
        return self


class MediaFrameAnchor(AuthoredRecord):
    """A named phase-relative source frame, independent of body frame limits."""
    name: Identifier
    frame: NonNegative


class AuthoredProjectilePhase(AuthoredRecord):
    start: Annotated[int, Field(ge=0)]
    frames: Annotated[int, Field(ge=1)]
    fps: Positive | None = None
    loop: bool
    anchors: tuple[MediaFrameAnchor, ...] = ()

    @model_validator(mode="after")
    def valid_anchors(self) -> AuthoredProjectilePhase:
        if len({row.name for row in self.anchors}) != len(self.anchors):
            raise ValueError("media phase requires unique anchors")
        if any(row.frame >= self.frames for row in self.anchors):
            raise ValueError("media anchor is outside its source phase")
        return self


class ProjectileFrame(AuthoredRecord):
    width: Annotated[int, Field(ge=1)]
    height: Annotated[int, Field(ge=1)]
    cols: Annotated[int, Field(ge=1)]
    rows: Literal[8]


class AuthoredProjectilePhases(AuthoredRecord):
    travel: AuthoredProjectilePhase | None = None
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
    anchorsByFacing: FacingMap[ProjectileAssetAnchor] | None = None
    defaultScale: Positive
    tags: tuple[str, ...] | None = None
    palettePreview: PalettePreview
    paletteSwap: PaletteSwap | None = None
    source: ProjectileSource | None = None
    validation: ProjectileValidation | None = None


class ProjectilePage(AuthoredRecord):
    file: Identifier
    firstFrame: Annotated[int, Field(ge=0)]
    frameCount: Annotated[int, Field(ge=1)]
    columns: Annotated[int, Field(ge=1)]


class ProjectileFrameLayer(AuthoredRecord):
    """Local storage/material binding; independent of the Studio spell recipe."""

    pattern: str | None = None
    pages: FacingMap[tuple[ProjectilePage, ...]] | None = None
    partsByFacing: FacingMap[tuple[tuple[ProjectileFramePart, ...], ...]] | None = None
    # Camera-readable media can share one sequence without eight copied banks.
    parts: tuple[tuple[ProjectileFramePart, ...], ...] | None = None
    blendMode: Literal["normal", "add"]
    gain: Annotated[float, Field(ge=0, le=1)] = 1
    depth: Literal["world", "behind_body", "front_body"] = "world"

    @model_validator(mode="after")
    def one_source(self) -> ProjectileFrameLayer:
        sources = (self.pattern, self.pages, self.parts, self.partsByFacing)
        if sum(value is not None for value in sources) != 1 or not any(sources):
            raise ValueError("frame layer requires exactly one nonempty source")
        if self.pages is not None and any(not pages for pages in self.pages.values()):
            raise ValueError("each selected page bank must contain pages")
        if self.partsByFacing is not None and any(not frames for frames in self.partsByFacing.values()):
            raise ValueError("each selected part bank must contain frame records")
        return self


class PackedFootpoint(AuthoredRecord):
    """Aligned raw RGBA: big-endian uint16 X in RG and Y in BA, in local cells."""

    file: Identifier
    bounds: tuple[float, float]
    coordinateBasis: Literal["world_xy"] = "world_xy"

    @model_validator(mode="after")
    def ordered_bounds(self) -> PackedFootpoint:
        if self.bounds[0] >= self.bounds[1]:
            raise ValueError("footpoint bounds must increase")
        return self


class RGBMediaTint(AuthoredRecord):
    color: Annotated[int, Field(ge=0, le=0xFFFFFF)]
    strength: Annotated[float, Field(ge=0, le=1)]


class MaskedMediaTint(RGBMediaTint):
    """RGB-only material mix through a registered linear single-channel mask."""

    mask: Identifier


class ProjectileFramePart(AuthoredRecord):
    """Lossless sparse packing in an asset's unchanged logical canvas."""

    file: Identifier
    rect: tuple[int, int, int, int]
    offset: tuple[int, int]
    footpoint: PackedFootpoint | None = None
    colorMasks: FrozenMap[Identifier] = Field(default_factory=dict)


class ProjectileFrameStorage(AuthoredRecord):
    layers: tuple[ProjectileFrameLayer, ...] = ()
    surfaceFrames: PackedSurfaceFrames | None = None

    @model_validator(mode="after")
    def one_source(self) -> ProjectileFrameStorage:
        if bool(self.layers) == (self.surfaceFrames is not None):
            raise ValueError("phase storage requires layers or surfaceFrames, exclusively")
        return self


class SurfaceArchive(AuthoredRecord):
    """Standard ZIP member address; the member retains the authored packet bytes."""

    file: Identifier
    memberPattern: Identifier


class PackedSurfaceFrames(AuthoredRecord):
    """Matched RGBA/XYZ/ownership packets; frame selection leaves source timing authored."""

    pattern: Identifier | None = None
    archive: SurfaceArchive | None = None
    frameIndices: Annotated[tuple[Annotated[int, Field(ge=0)], ...], Field(min_length=1)]
    bounds: tuple[float, float]
    verticalScale: Positive
    blendModes: tuple[Literal["normal", "add"], ...] = ()
    componentsByFacing: FacingMap[tuple[PackedSurfaceComponent, ...]] | None = None
    positionScale: Positive = 1
    referencePixelScale: Positive = 1
    coordinateBasis: Literal["camera_local_xyz", "material_rest_xyz"] = "camera_local_xyz"

    @model_validator(mode="after")
    def packet_source(self) -> PackedSurfaceFrames:
        if sum(value is not None for value in (self.pattern, self.archive, self.componentsByFacing)) != 1:
            raise ValueError("surface frames require one pattern, archive or component source")
        if self.bounds[0] >= self.bounds[1]:
            raise ValueError("surface bounds must increase")
        if self.componentsByFacing is not None:
            if not self.componentsByFacing or any(not bank for bank in self.componentsByFacing.values()):
                raise ValueError("surface component banks must be nonempty")
        elif not self.blendModes:
            raise ValueError("single surface source requires its ordered blend modes")
        return self


class PackedSurfaceComponent(AuthoredRecord):
    """One ordered source component, registered to the whole effect origin."""

    pattern: Identifier | None = None
    archive: SurfaceArchive | None = None
    pivot: tuple[float, float]
    blendMode: Literal["normal", "add"]

    @model_validator(mode="after")
    def one_source(self) -> PackedSurfaceComponent:
        if (self.pattern is None) == (self.archive is None):
            raise ValueError("surface component requires one pattern or archive")
        return self


class ProjectileStorage(AuthoredRecord):
    phases: FrozenMap[ProjectileFrameStorage]


class ActionFrameAnchor(AuthoredRecord):
    name: Identifier
    frame: BodyFrame


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
    CLIP_ANCHORS: FrozenMap[tuple[ActionFrameAnchor, ...]] = Field(default_factory=dict)


class BodyClip(AuthoredRecord):
    """One semantic body clip resolved to exact local sheet bindings."""

    source_clip: Identifier
    frames: Annotated[int, Field(ge=1)]
    fps: Positive
    sheets: FrozenMap[str]
    # Original accents registered to this body's frames, e.g. a muzzle flash.
    # They own no attack, delivery, or effect timing of their own.
    layers: tuple[RigLayer, ...] = ()
    owns_cast_preparation: bool = False
    source_sockets: SourceSockets | None = None
    anchors: tuple[ActionFrameAnchor, ...] = ()

    @model_validator(mode="after")
    def valid_anchors(self) -> BodyClip:
        if len({row.name for row in self.anchors}) != len(self.anchors):
            raise ValueError("body clip requires unique anchors")
        if any(row.frame >= self.frames for row in self.anchors):
            raise ValueError("body clip anchor is outside its frames")
        return self


PoseSockets = FrozenMap[FrozenMap[FacingMap[tuple[Point | None, ...]]]]


class ActionActor(AuthoredRecord):
    enabled: bool
    clip: Identifier
    playbackSpeed: Positive
    hiddenSlots: tuple[str, ...]
    media: tuple[JsonValue, ...]


BodyContextRole = Literal[
    "movement", "movement_recovery", "shove", "forced_movement", "forced_movement_recovery",
    "body_action", "body_action_recovery", "equipment", "condition_entry", "condition_hold",
    "condition_exit", "healing", "save_avoidance", "cast", "death",
]


class RoleDefault(AuthoredRecord):
    kind: Literal["default"] = "default"


class ContentBodyQualifier(AuthoredRecord):
    kind: Literal["content"] = "content"
    contentRef: ContentRef


class MovementBodyQualifier(AuthoredRecord):
    kind: Literal["movement"] = "movement"
    movement_mode: MovementMode | None
    trajectory: MovementTrajectory
    connector_presentation_key: Identifier | None


BodyContextQualifier = Annotated[
    RoleDefault | ContentBodyQualifier | MovementBodyQualifier, Field(discriminator="kind"),
]


class BodyContext(AuthoredRecord):
    """Only body selection and frame playback; native paths and joins stay outside."""

    actor: ActionActor
    anchors: tuple[ActionFrameAnchor, ...] = ()
    playback: Literal["once", "loop", "final_rest"] = "once"
    reversed: bool = False
    frameKeys: tuple[tuple[Annotated[float, Field(ge=0, le=1)], BodyFrame], ...] = ()
    restFrame: BodyFrame | None = None

    @model_validator(mode="after")
    def validate_playback(self) -> BodyContext:
        if len({anchor.name for anchor in self.anchors}) != len(self.anchors):
            raise ValueError("body context has duplicate frame anchors")
        if self.frameKeys:
            times = tuple(key[0] for key in self.frameKeys)
            if self.playback != "once" or times[0] != 0 or times[-1] != 1 or any(a >= b for a, b in zip(times, times[1:])):
                raise ValueError("body frame keys require once playback and increasing times from 0 to 1")
        if self.restFrame is not None and self.reversed:
            raise ValueError("an explicit final-rest frame cannot also reverse playback")
        if (self.restFrame is not None) != (self.playback == "final_rest"):
            raise ValueError("final-rest playback requires exactly one explicit rest frame")
        return self


class RigBodyContextBinding(AuthoredRecord):
    role: BodyContextRole
    qualifier: BodyContextQualifier
    body: BodyContext

    @model_validator(mode="after")
    def validate_context(self) -> RigBodyContextBinding:
        if self.role == "death" and (self.body.playback != "once" or self.body.reversed or self.body.frameKeys):
            raise ValueError("terminal death requires finite forward source playback")
        movement = self.role in ("movement", "movement_recovery")
        content_roles = {"shove", "body_action", "body_action_recovery", "condition_entry",
                         "condition_hold", "condition_exit", "save_avoidance", "cast"}
        if (isinstance(self.qualifier, MovementBodyQualifier) and not movement
                or isinstance(self.qualifier, ContentBodyQualifier) and self.role not in content_roles):
            raise ValueError("body qualifier does not belong to this context role")
        if self.body.actor.hiddenSlots or self.body.actor.media:
            raise ValueError("rig body contexts cannot mutate hidden slots or media")
        optional = {"movement_recovery", "forced_movement_recovery", "body_action", "body_action_recovery",
                    "equipment", "healing", "save_avoidance"}
        if not self.body.actor.enabled and self.role not in optional:
            raise ValueError(f"required {self.role} body cannot be disabled")
        required = {"shove": {"contact"}, "forced_movement": {"brace"},
                    "body_action": {"effect"}, "equipment": {"commit"}, "cast": {"prepare", "release"}}
        names = {anchor.name for anchor in self.body.anchors}
        supported = required.get(self.role, set())
        if names != supported and (self.body.actor.enabled or names):
            raise ValueError(f"{self.role} requires exactly its supported body markers")
        playback = self.body.playback
        if self.role == "condition_hold":
            if playback != "final_rest":
                raise ValueError("condition hold requires an explicit final-rest frame")
        elif playback == "final_rest" or playback == "loop" and self.role != "movement":
            raise ValueError(f"unsupported {self.role} playback: {playback}")
        if self.body.frameKeys and self.role not in ("movement", "save_avoidance"):
            raise ValueError("frame keys belong to normalized travel body contexts")
        return self


class BodyRig(AuthoredRecord):
    """Passive body layout/capabilities, shared by timing and pixel sampling."""

    cell_width: Annotated[int, Field(ge=1)]
    cell_height: Annotated[int, Field(ge=1)]
    origin_y_from_ground: float
    shadow_alpha: Annotated[float, Field(ge=0, le=1)] = 0.5
    body_anchor: Point | None = None
    lifecycle_scale: Annotated[float, Field(ge=.5, le=1.65)] = 1.
    native_wings: bool = False
    rest_pose_anchors: FrozenMap[FacingMap[Point]] = Field(default_factory=dict)
    # Socket / semantic clip / viewed facing / sampled frame, in full-cell pixels.
    pose_sockets: PoseSockets = Field(default_factory=dict)
    facing_rows: FacingMap[int]
    slot_order: tuple[str, ...]
    slot_categories: FrozenMap[tuple[str, ...]]
    clips: FrozenMap[BodyClip]
    body_contexts: tuple[RigBodyContextBinding, ...] = ()

    @field_serializer("rest_pose_anchors")
    def serialize_rest_pose_anchors(self, value: Mapping[str, Mapping[Facing8, Point]]) -> dict[str, dict[Facing8, Point]]:
        return {pose: dict(points) for pose, points in value.items()}

    @field_serializer("pose_sockets")
    def serialize_pose_sockets(self, value: PoseSockets) -> dict[str, dict[str, dict[Facing8, tuple[Point | None, ...]]]]:
        return {socket: {clip: dict(rows) for clip, rows in clips.items()}
                for socket, clips in value.items()}

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
            if len({layer.slot for layer in clip.layers}) != len(clip.layers):
                raise ValueError("body clip layers require unique slots")
            for layer in clip.layers:
                if (layer.slot in {"body", "shadow"}
                        or layer.category not in self.slot_categories.get(layer.slot, ())
                        or layer.category not in clip.sheets
                        or layer.alpha != 1 or layer.tint != 0xFFFFFF
                        or layer.item_uuid is not None or layer.item_effects):
                    raise ValueError("body clip accents require their own declared slot and sheet")
            if clip.owns_cast_preparation and not clip.layers:
                raise ValueError("clip-owned cast preparation requires original accent layers")
        if "ground_depth" in self.pose_sockets and "Idle" not in self.pose_sockets["ground_depth"]:
            raise ValueError("ground depth points require an Idle reference")
        for socket, clips in self.pose_sockets.items():
            for name, rows in clips.items():
                if name not in self.clips or set(rows) != facings:
                    raise ValueError("pose sockets require an existing clip and all eight facings")
                if any(len(points) != self.clips[name].frames for points in rows.values()):
                    raise ValueError("pose sockets require one entry per body frame")
                if socket == "ground_depth" and any(point is None for points in rows.values() for point in points):
                    raise ValueError("ground depth requires a measured point for every frame")
        keys: set[tuple[str, str]] = set()
        for binding in self.body_contexts:
            key = binding.role, binding.qualifier.model_dump_json()
            if key in keys:
                raise ValueError(f"duplicate rig body context: {binding.role}")
            keys.add(key)
            body = binding.body
            if body.actor.enabled:
                clip = self.clips.get(body.actor.clip)
                if clip is None:
                    raise ValueError(f"{binding.role}: missing body clip {body.actor.clip}")
                frames = [*(row.frame for row in body.anchors), *(frame for _, frame in body.frameKeys)]
                if body.restFrame is not None:
                    frames.append(body.restFrame)
                if any(frame >= clip.frames for frame in frames):
                    raise ValueError(f"{binding.role}: unreachable body frame in {body.actor.clip}")
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


class SilhouetteDust(AuthoredRecord):
    """Accepted outline erosion and finite particles, shared by bodies and objects."""
    erosionMs: Positive
    particleLifetimeMs: Positive
    particleFadeInMs: Positive
    alphaThreshold: Annotated[int, Field(ge=1, le=255)]
    horizontalRankWeight: Annotated[float, Field(ge=0, le=1)]
    velocityX: NonNegative
    velocityY: tuple[float, float]
    gravity: NonNegative
    color: Color
    minimumLuminance: Annotated[float, Field(ge=0, le=1)]
    particleEvery: Annotated[int, Field(ge=1)]
    particleSize: Positive

    @property
    def duration_ms(self) -> float:
        return self.erosionMs + self.particleLifetimeMs


class DeathContext(AuthoredRecord):
    silhouetteDust: SilhouetteDust | None = None
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
    spellTintStrength: Annotated[float, Field(ge=0, le=1)] = 0
    startFrame: Annotated[int, Field(ge=0, le=120)]
    fps: Positive
    loop: bool
    reversed: bool
    scale: Annotated[float, Field(ge=0.1, le=8)]
    offsetX: Annotated[float, Field(ge=-512, le=512)]
    offsetY: Annotated[float, Field(ge=-512, le=512)]
    whenConditions: tuple[Identifier, ...] = ()
    unlessConditions: tuple[Identifier, ...] = ()
    viewFacing: Facing8 | None = None
    depth: Literal["ground", "behind_body", "front_body"] = "ground"
    contactFrame: NonNegative = 0
    emitIntervalMs: Positive | None = None
    fitToMotion: bool = False
    alpha: Annotated[float, Field(ge=0, le=1)] = 1


class ActionMediaAsset(AuthoredRecord):
    """NeuroClient actionMediaAssets v1 source row, including one-row strips."""

    assetId: Identifier
    displayName: str
    source: Identifier
    directional: bool
    frames: Annotated[int, Field(ge=1, le=256)]
    defaultFps: Positive
    tags: tuple[str, ...]


class ActionMediaAssetFile(AuthoredRecord):
    schema_: Literal["neuroclient.actionMediaAssets"] = Field(alias="schema")
    version: Literal[1]
    assets: tuple[ActionMediaAsset, ...]


class WorldParticle(AuthoredRecord):
    """Authored trajectory in world tiles/seconds; evaluated at absolute time."""

    id: int
    x: float
    y: float
    z: float
    vx: float
    vy: float
    vz: float
    g: Positive
    life: Positive
    delay: NonNegative
    size: Positive
    radius: Positive
    theta: float
    seed: int


class LandingKernel(AuthoredRecord):
    x: float
    y: float
    rx: Positive
    ry: Positive
    angle: float
    mass: Positive


class LandingParticle(AuthoredRecord):
    id: int
    target: tuple[float, float]
    duration: Positive
    gravity: Positive
    delay: NonNegative
    size: Positive
    kernels: tuple[LandingKernel, ...]
    fragment: tuple[tuple[float, float], ...]


class LandingTemplate(AuthoredRecord):
    seed: int
    particles: tuple[LandingParticle, ...]


class ReleaseFamily(AuthoredRecord):
    delayScale: Positive
    durationScale: Positive


class BloodVapor(AuthoredRecord):
    color: Annotated[int, Field(ge=0, le=0xFFFFFF)]
    every: Annotated[int, Field(ge=1)] = 7
    count: Annotated[int, Field(ge=1)] = 4
    life: Positive
    interval: Positive = .2
    startFraction: NonNegative = .65
    rise: NonNegative = .23
    opacity: Annotated[float, Field(ge=0, le=1)] = .58


class BloodResponse(AuthoredRecord):
    """Finite blood-only styling; deposition geometry remains native state."""

    shape: Literal["spray", "ragged", "bead", "frozen"] = "spray"
    durationScale: Positive = 1
    delayScale: Positive = 1
    gravityScale: Positive = 1
    sizeScale: Positive = 1
    tailScale: Positive = 1
    heavyEvery: Annotated[int, Field(ge=0)] = 0
    heavyScale: Positive = 1
    colors: tuple[Color, Color]
    detail: Literal["none", "acid", "fire", "lightning", "necrotic", "poison", "psychic", "radiant", "thunder"] = "none"
    meltBase: NonNegative = 0
    meltSize: NonNegative = 0
    surfaceSeconds: NonNegative = 0
    vapor: BloodVapor | None = None


class RegionParticleStyle(AuthoredRecord):
    """Normalized landing detail; native regions own its world placement."""

    templates: tuple[LandingTemplate, ...]
    families: FrozenMap[ReleaseFamily]
    primitive: Literal["liquid", "fragments"]
    palette: tuple[Color, Color, Color] | None
    sourceHeight: Positive = .65
    criticalCopies: int = 2


class ParticleMediaAsset(AuthoredRecord):
    """Portable media extension for independent world-depth particle tracks."""

    assetId: Identifier
    frames: Annotated[int, Field(ge=1, le=256)]
    defaultFps: Positive
    particles: tuple[WorldParticle, ...] = ()
    region: RegionParticleStyle | None = None
    legacyAssetId: str | None = None
    colors: tuple[Color, Color]
    tailSeconds: Positive
    tailMinPx: Positive
    tailMaxPx: Positive
    snapPx: Positive


class ParticleMediaAssetFile(AuthoredRecord):
    schema_: Literal["neurodragon.particleMediaAssets"] = Field(alias="schema")
    version: Literal[1]
    assets: tuple[ParticleMediaAsset, ...]


class MovementRecovery(AuthoredRecord):
    enabled: bool
    bodyClip: Literal["Taunt", "Special1", "Rolling"]
    bodyPlaybackSpeed: BodySpeed
    media: tuple[MovementMediaTrack, ...]


class HealingContext(AuthoredRecord):
    bodyClip: Literal["none", "Taunt", "Special1"]
    bodyPlaybackSpeed: BodySpeed
    feedbackEnabled: bool
    feedbackColor: Color
    feedbackLabel: Identifier
    feedbackDurationMs: Annotated[float, Field(ge=0, le=5000)]
    media: tuple[MovementMediaTrack, ...]


class LifecycleFeedback(AuthoredRecord):
    enabled: bool
    text: Identifier
    color: Annotated[int, Field(ge=0, le=0xFFFFFF)]


class DeathSaveContext(AuthoredRecord):
    success: LifecycleFeedback
    failure: LifecycleFeedback
    criticalSuccess: LifecycleFeedback
    criticalFailure: LifecycleFeedback


class LifeStateBodyPose(AuthoredRecord):
    bodyPose: Identifier
    applicationBody: ConditionBodyAnimation | None = None
    removalBody: ConditionBodyAnimation | None = None


LifeBodyPoses = Annotated[
    Mapping[Literal["dying", "stable"], LifeStateBodyPose], AfterValidator(MappingProxyType),
    PlainSerializer(dict, return_type=dict),
]


class LifeStateContext(AuthoredRecord):
    dying: LifecycleFeedback
    stable: LifecycleFeedback
    revived: LifecycleFeedback
    bodyPoses: LifeBodyPoses = Field(default_factory=lambda: MappingProxyType({}))


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


class ForcedMovementContext(AuthoredRecord):
    label: str
    feedbackEnabled: bool
    feedbackColor: Color
    motionCurve: Literal["linear", "ease_out_quad", "ease_out_cubic"]
    facingPolicy: Literal["source_or_opposite_travel", "opposite_travel", "preserve"]
    durationScale: Annotated[float, Field(ge=0.25, le=4)]
    playbackSpeedScale: Annotated[float, Field(ge=0.25, le=4)]
    media: tuple[MovementMediaTrack, ...]
    recovery: MovementRecovery


class ForcedMovementProfile(AuthoredRecord):
    """Original Studio cue values kept in portable local data, outside mechanics."""

    duration_ms: Positive
    target_clip: Identifier
    brace_frame: BodyFrame
    playback_speed: Positive
    provenance: FrozenMap[str]


class ConnectorMovementProfile(AuthoredRecord):
    animationId: Identifier
    bodyClip: str
    durationMs: Annotated[float, Field(ge=100, le=3000)]
    arcHeightPx: Annotated[float, Field(ge=0, le=200)] = 0
    bodyLoops: bool = False
    passageBodyHeightPx: Annotated[float, Field(ge=0, le=200)] | None = None
    passageScale: tuple[Annotated[float, Field(ge=0.25, le=1)],
                        Annotated[float, Field(ge=0.25, le=1)]] = (1, 1)
    passageSocket: Identifier | None = None
    passageHoldFraction: Annotated[float, Field(ge=0, le=0.9)] = 0
    bodyFrameKeys: tuple[tuple[Annotated[float, Field(ge=0, le=1)], BodyFrame], ...] = ()

    @model_validator(mode="after")
    def validate_frame_keys(self) -> ConnectorMovementProfile:
        if self.bodyFrameKeys:
            times = tuple(key[0] for key in self.bodyFrameKeys)
            if self.bodyLoops or times[0] != 0 or times[-1] != 1 or any(a >= b for a, b in zip(times, times[1:])):
                raise ValueError("connector body frame keys must increase from 0 to 1 without looping")
        return self


class FlightMovementProfile(AuthoredRecord):
    """Visual ground-to-ground lift over a disclosed, continuous path."""

    clearancePx: Annotated[float, Field(gt=0, le=200)]
    takeoffFraction: Annotated[float, Field(gt=0, lt=1)]
    landingFraction: Annotated[float, Field(gt=0, lt=1)]
    body: BodyContext

    @model_validator(mode="after")
    def validate_phases(self) -> FlightMovementProfile:
        if self.takeoffFraction + self.landingFraction > 1:
            raise ValueError("flight takeoff and landing must fit within its path")
        if self.body.playback != "once" or not self.body.actor.enabled:
            raise ValueError("flight requires one normalized airborne body sequence")
        return self


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
    connectorProfiles: dict[str, ConnectorMovementProfile] = Field(default_factory=dict)
    flight: FlightMovementProfile | None = None

    @model_validator(mode="after")
    def validate_jump_duration(self) -> VoluntaryMovementContext:
        if self.jumpMinDurationMs > self.jumpMaxDurationMs:
            raise ValueError("jumpMinDurationMs must not exceed jumpMaxDurationMs")
        return self


class MovementPresentation(AuthoredRecord):
    schema_: Literal["dnd.movementPresentation"] = Field(alias="schema")
    version: Literal[1]
    referenceSpeedFeet: Positive
    actionPlaybackRates: FrozenMap[Positive]
    walkMedia: tuple[MovementMediaTrack, ...]
    jumpMedia: tuple[MovementMediaTrack, ...]
    flight: FlightMovementProfile | None = None


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


class AttackProfileMatch(AuthoredRecord):
    kind: Literal["attack"]
    delivery: Literal["melee", "projectile"] | None
    weaponSlots: tuple[str, ...] | None
    outcomes: tuple[str, ...] | None
    primaryDamageTypes: tuple[str, ...] | None
    elemental: bool | None
    sourceItemRefs: tuple[ContentRef, ...] | None
    # Current gear uses stable item identities; imported Studio refs remain readable.
    sourceItemIds: tuple[str, ...] | None = None
    sourceKinds: tuple[Literal["equipped", "unarmed", "natural"], ...] | None = None
    rigIds: tuple[Identifier, ...] | None = None


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
    sourceSocketsByRig: FrozenMap[SourceSockets] = Field(default_factory=dict)


class AttackVariant(AuthoredRecord):
    id: Identifier
    precedence: int
    match: AttackProfileMatch
    actor: ActionActor
    anchors: tuple[ActionFrameAnchor, ...]
    attackVfx: AttackVfx
    projectile: ActionProjectile | None


class WeaponTrailPose(AuthoredRecord):
    rigId: Identifier
    category: Identifier
    clip: Identifier
    pointsByFacing: FacingMap[tuple[Point | None, ...]]

    @model_validator(mode='after')
    def complete_facings(self) -> WeaponTrailPose:
        if set(self.pointsByFacing) != {'E','SE','S','SW','W','NW','N','NE'}:
            raise ValueError('Weapon paths require all eight measured facings')
        return self


class WeaponTrailPresentation(AuthoredRecord):
    """Measured equipped-weapon paths and the accepted finite contact bank."""
    poses: tuple[WeaponTrailPose, ...]
    impactAssetId: Identifier
    palette: tuple[int, int, int]
    behaviorIds: tuple[Identifier, ...] = ()
    handlerIds: tuple[Identifier, ...] = ()
    outcomes: tuple[Literal['hit','miss','critical','critical_miss'], ...] = ()


class WeaponTrailBinding(AuthoredRecord):
    behaviors: tuple[Identifier, ...]
    presentation: WeaponTrailPresentation


class AttackProfileFile(AuthoredRecord):
    """Local shared profiles in the original NeuroStudio variant vocabulary."""

    behaviors: tuple[Identifier, ...]
    variants: tuple[AttackVariant, ...]


class ActionFeedback(AuthoredRecord):
    text: Identifier
    color: Annotated[int, Field(ge=0, le=0xFFFFFF)]


class CounterspellFeedback(AuthoredRecord):
    automatic_success: ActionFeedback
    check_success: ActionFeedback
    check_failure: ActionFeedback


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
    weaponTrail: WeaponTrailPresentation | None = None


class InterruptionRule(AuthoredRecord):
    phases: tuple[Literal["declaration", "execution"], ...]
    actionEconomySpent: bool
    anticipationFraction: float = Field(gt=0, lt=1)
    travelFraction: float | None = Field(default=None, gt=0, lt=1)
    nonProjectileBodyFraction: float | None = Field(default=None, gt=0, lt=1)


class ReactionMedia(AuthoredRecord):
    successByCamera: tuple[Identifier, Identifier, Identifier, Identifier]
    failureByCamera: tuple[Identifier, Identifier, Identifier, Identifier]
    dissipationMask: Identifier
    durationMs: Positive
    scale: Positive = 1
    castLayers: tuple[StudioActorLayer, ...] = ()


class InterruptionPresentation(AuthoredRecord):
    outcomes: tuple[str, ...]
    rules: tuple[InterruptionRule, ...]
    reactions: FrozenMap[ReactionMedia] = Field(default_factory=dict)


class ContentActionRecipe(AuthoredRecord):
    """Original content-action row shared by actor gestures and Shove."""

    definitionRef: ContentRef
    compatibleCueKinds: tuple[str, ...]
    previewChildCueKinds: tuple[str, ...]
    disposition: Literal["authored"]
    mediaFailurePolicy: Literal["fail_transaction", "omit_optional_track"]
    actor: ActionActor
    anchors: tuple[ActionFrameAnchor, ...]
    attackFeedback: JsonValue
    counterspellFeedback: CounterspellFeedback | None
    variants: tuple[JsonValue, ...]
    projectile: JsonValue
    actionFeedback: ActionFeedback | None
    media: tuple[BodyActionMediaTrack, ...] = ()
    handlerResponse: bool = False


ShoveRecipe = ContentActionRecipe
BodyActionRecipe = ContentActionRecipe


class BodyActionBinding(AuthoredRecord):
    source_recipe: Identifier
    action_feedback: ActionFeedback | None
    interaction_target: Literal["source_item", "target_item"] | None = None


@dataclass(frozen=True, slots=True)
class MechanismProjectileArt:
    """Registered directional media and release socket of a placed mechanism."""

    frames_by_pose: Mapping[str, tuple[str, ...]]
    tip_offsets_by_pose: Mapping[str, tuple[tuple[float, float], ...]]
    muzzle_offsets_by_pose: Mapping[str, tuple[float, float]]
    muzzle_height_steps: float
    speed_tiles_per_second: float


@dataclass(frozen=True, slots=True)
class SaveHop:
    """An authored body reaction to one exact successful saving throw."""

    effect_id: str
    body_clip: str
    duration_ms: float
    height_px: float


@dataclass(frozen=True, slots=True)
class PropDepth:
    """A registered RG-packed horizontal-depth atlas, independent of gameplay."""

    asset_id: str
    cell: tuple[int, int]
    rows_by_pose: Mapping[str, int]
    depth_range: tuple[float, float]
    pixels_per_unit_by_pose: Mapping[str, float]


@dataclass(frozen=True, slots=True)
class PropAnimation:
    """Shared finite world poses and timing, independent of a renderer."""

    frames_by_pose: Mapping[str, tuple[str, ...]]
    fps: int
    state_frames: Mapping[str, int]
    default_frame: int = 0
    placement: Literal["cell", "area", "anchor"] = "cell"
    origin_offset: tuple[float, float] = (0, 0)
    creation_start_frame: int | None = None
    footprint_tiles: tuple[int, int] | None = None
    activation_frames: tuple[int, ...] = ()
    contact_frame: int | None = None
    transition_frames: Mapping[str, tuple[int, ...]] = field(default_factory=dict)
    projectile: MechanismProjectileArt | None = None
    depth: Literal["ground", "world"] = "ground"
    successful_save_hop: SaveHop | None = None
    actor_depth: PropDepth | None = None


@dataclass(frozen=True, slots=True)
class TetherAnimation:
    """Authored cable media registered by its two endpoint pixels."""

    frames_by_facing: Mapping[Facing8, tuple[str, ...]]
    endpoints_by_facing: Mapping[Facing8, tuple[tuple[float, float], tuple[float, float]]]
    fps: float


class WallModuleAssets(AuthoredRecord):
    """One paired lifecycle bank; axis selection never rotates baked pixels."""

    assetId: Identifier
    applicationAssetId: Identifier


class WallAxisMedia(AuthoredRecord):
    axis: Literal["x", "y", "diagonal_positive", "diagonal_negative"]
    variants: Annotated[tuple[WallModuleAssets, ...], Field(min_length=1)]
    spacingCells: Annotated[float, Field(gt=0, le=1)] = 1
    maxAngleDegrees: Annotated[float, Field(ge=0, le=22.5)] = 0
    positiveMaskNormal: tuple[float, float] | None = None

    @model_validator(mode="after")
    def registered_mask_normal(self) -> "WallAxisMedia":
        if self.axis not in ("x", "y") and self.positiveMaskNormal is None:
            raise ValueError("diagonal wall banks require their registered positive mask normal")
        if self.positiveMaskNormal is not None:
            x, y = self.positiveMaskNormal
            tangent = {"x": (1, 0), "y": (0, 1), "diagonal_positive": (1, 1),
                       "diagonal_negative": (1, -1)}[self.axis]
            if x*x+y*y == 0 or abs(x*tangent[0]+y*tangent[1]) > 1e-6:
                raise ValueError("wall mask normal must be nonzero and perpendicular to its native axis")
        return self


class WallRingMedia(AuthoredRecord):
    assetId: Identifier
    applicationAssetId: Identifier
    radiusFeet: Positive
    widthFeet: Positive


class AssemblyModuleMedia(AuthoredRecord):
    """One native orientation with independently selected lifecycle phases."""

    tangent: tuple[float, float]
    assetId: Identifier
    applicationAssetId: Identifier | None = None
    removalAssetId: Identifier | None = None


class AssemblyRingMedia(AuthoredRecord):
    heightFeet: Positive
    assetId: Identifier
    applicationAssetId: Identifier
    removalAssetId: Identifier
    radiusFeet: Positive
    widthFeet: Positive
    pixelScale: Positive


class WindFlowMaterial(AuthoredRecord):
    """Original joined sheets evaluated on the received wall path and body contacts."""
    material: Literal["wind_streaks"]
    components: Identifier
    nativeUnitsPerCell: Positive
    verticalScale: Positive
    palette: Annotated[tuple[int, ...], Field(min_length=2)]


class ConstructionAirMedia(AuthoredRecord):
    """Original quiet air geometry and flake law, owned by an actual breach."""
    mesh: Identifier
    sourceRadiusFeet: Positive
    nativeUnitsPerCell: Positive
    verticalScale: Positive
    palette: Annotated[tuple[int, ...], Field(min_length=2)]


class ThornsMaterial(AuthoredRecord):
    """Original living vine mesh responding to admitted body/damage contacts."""
    components: Identifier
    nativeUnitsPerCell: Positive
    verticalScale: Positive
    palette: Annotated[tuple[int, ...], Field(min_length=2)]


class WallAssemblyMedia(AuthoredRecord):
    """Registered passive construction data, separate from Fire's paired banks."""

    modules: Annotated[tuple[AssemblyModuleMedia, ...], Field(min_length=1)]
    moduleLengthCells: Positive
    heightFeet: Positive
    widthFeet: Positive
    pixelScale: Positive
    ring: AssemblyRingMedia | None = None
    flow: WindFlowMaterial | None = None
    air: ConstructionAirMedia | None = None
    thorns: ThornsMaterial | None = None

    @model_validator(mode="after")
    def distinct_directions(self) -> "WallAssemblyMedia":
        tangents = [row.tangent for row in self.modules]
        if len(set(tangents)) != len(tangents) or any(x*x+y*y <= 0 for x, y in tangents):
            raise ValueError("assembly modules require distinct nonzero native tangents")
        return self


class OrbitMedia(AuthoredRecord):
    """Original component motion in the current owner's local space."""
    blendMode: Literal["normal", "screen"] = "normal"
    count: Annotated[int, Field(ge=1)]
    radiusCells: Positive
    heightCells: float
    periodMs: Positive
    slotsPerCycle: Annotated[int, Field(ge=1)]
    sizePixels: Positive
    formationMs: Positive
    trailMs: Positive
    trailSamples: Annotated[int, Field(ge=2)]
    bright: Annotated[int, Field(ge=0, le=0xFFFFFF)]
    middle: Annotated[int, Field(ge=0, le=0xFFFFFF)]
    mistLow: tuple[int, int, int]
    mistRange: tuple[int, int, int]
    mistRadiusCells: Positive


class GroundEllipse(AuthoredRecord):
    radiiCells: tuple[Positive, Positive]
    color: Annotated[int, Field(ge=0, le=0xFFFFFF)]
    alpha: Annotated[float, Field(ge=0, le=1)]


class DirectedSpatialResponse(AuthoredRecord):
    """A finite admitted object gesture, never a hit-test shape."""
    blendMode: Literal["normal", "screen"] = "normal"
    assetId: Identifier
    firstFrame: Annotated[int, Field(ge=0)]
    frames: Annotated[int, Field(ge=1)]
    fps: Positive
    contactFrame: Annotated[int, Field(ge=0)]
    scale: Positive
    bladeMotion: tuple[tuple[tuple[float, float, float], tuple[float, float, float]], ...] = ()
    bladeWorldScale: Positive = 1
    palette: tuple[int, int, int]

    @model_validator(mode="after")
    def phase_bounds(self) -> DirectedSpatialResponse:
        if self.contactFrame >= self.frames or self.bladeMotion and len(self.bladeMotion) != self.frames:
            raise ValueError("Directed response contact/blade samples must fit the finite phase")
        return self


class CellMediaVariant(AuthoredRecord):
    """One accepted formation and sustained source pair for a native cell."""
    assetId: Identifier
    applicationAssetId: Identifier


class SpatialMediaLayer(AuthoredRecord):
    """One registered layer around the received area's occupants."""
    assetId: Identifier
    applicationAssetId: Identifier | None = None
    side: Literal["center", "rear", "front"] = "center"
    removalAssetId: Identifier | None = None
    suppressionAssetId: Identifier | None = None
    recipientTrackId: Identifier | None = None
    whenEnergyType: DamageType | None = None
    whenPresenceMode: DraconicPresenceMode | None = None
    alpha: Annotated[float, Field(ge=0, le=1)] = 1
    scale: Positive = 1
    phaseOffsetMs: NonNegative = 0
    worldFacing: Facing8 = "E"
    orbit: OrbitMedia | None = None
    groundShadow: GroundEllipse | None = None
    motes: RisingMotes | None = None
    composition: Literal["billboard", "line_floor", "floor", "xy_volume", "xyz_volume", "clump", "wall_modules", "wall_assembly", "cell_modules", "orbit", "legacy", "volume"] = "legacy"
    cellVariants: tuple[CellMediaVariant, ...] = ()
    wallAxes: tuple[WallAxisMedia, ...] = ()
    wallRing: WallRingMedia | None = None
    wallAssembly: WallAssemblyMedia | None = None

    @model_validator(mode="after")
    def wall_banks(self) -> "SpatialMediaLayer":
        if bool(self.cellVariants) != (self.composition == "cell_modules"):
            raise ValueError("Cell modules require explicit source variants")
        if self.cellVariants and not any(row.assetId == self.assetId and row.applicationAssetId == self.applicationAssetId
                                       for row in self.cellVariants):
            raise ValueError("Cell lifecycle reference must identify a declared variant")
        if (self.orbit is not None) != (self.composition == "orbit"):
            raise ValueError("Orbit composition requires its authored component motion")
        if self.recipientTrackId is not None and self.composition != "clump":
            raise ValueError("recipient endpoints require clump composition")
        if (self.wallAssembly is not None) != (self.composition == "wall_assembly"):
            raise ValueError("wall_assembly composition requires its explicit registration")
        if self.composition == "wall_modules":
            axes = {row.axis for row in self.wallAxes}
            if not {"x", "y"} <= axes or len(axes) != len(self.wallAxes):
                raise ValueError("wall modules require distinct native banks including X/Y")
            if not any(variant.assetId == self.assetId and variant.applicationAssetId == self.applicationAssetId
                       for axis in self.wallAxes for variant in axis.variants):
                raise ValueError("wall lifecycle reference must identify a declared module variant")
        elif self.wallAxes or self.wallRing is not None:
            raise ValueError("wall axis banks require wall_modules composition")
        if self.wallRing is not None and self.side == "center":
            raise ValueError("whole-ring banks require rear/front layer ownership")
        return self
    @field_validator("composition", mode="before")
    @classmethod
    def previous_volume_name(cls, value: str) -> str:
        return "xy_volume" if value == "volume" else value

    offsetCells: tuple[float, float] = (0, 0)
    delayMs: NonNegative = 0


class ContactSweepVariant(AuthoredRecord):
    rearAssetId: Identifier
    frontAssetId: Identifier


class ContactSweepDirection(AuthoredRecord):
    direction: Literal["E", "S", "W", "N"]
    variants: Annotated[tuple[ContactSweepVariant, ...], Field(min_length=1)]


class ContactSweepNode(AuthoredRecord):
    fraction: Annotated[float, Field(ge=0, le=1)]
    delayMs: NonNegative
    variant: Annotated[int, Field(ge=0)]


class ContactSweep(AuthoredRecord):
    """Finite native-pixel accents between received source and recipient contacts."""

    directions: Annotated[tuple[ContactSweepDirection, ...], Field(min_length=4, max_length=4)]
    nodes: Annotated[tuple[ContactSweepNode, ...], Field(min_length=1)]
    scale: Positive = 1
    fadeStartMs: NonNegative
    fadeEndMs: Positive
    contactDelayMs: NonNegative = 0

    @model_validator(mode="after")
    def complete_banks(self) -> ContactSweep:
        if {bank.direction for bank in self.directions} != {"E", "S", "W", "N"}:
            raise ValueError("contact sweep requires four distinct cardinal banks")
        if self.fadeStartMs >= self.fadeEndMs:
            raise ValueError("contact sweep fade must have positive duration")
        if self.contactDelayMs >= max(node.delayMs for node in self.nodes)+self.fadeEndMs:
            raise ValueError("contact sweep must reach its recipient before clearing")
        if any(node.variant >= len(bank.variants) for node in self.nodes for bank in self.directions):
            raise ValueError("contact sweep node references a missing variant")
        return self


class SpatialMediaBinding(AuthoredRecord):
    """A maintained window in existing finite media; native observation owns existence."""

    layers: Annotated[tuple[SpatialMediaLayer, ...], Field(min_length=1)]
    assetPhase: Literal["cast", "travel", "impact"] = "impact"
    holdStartFrame: Annotated[int, Field(ge=0)]
    holdFrames: Annotated[int, Field(ge=1)]
    fps: Positive
    scale: Positive
    loopCrossfadeMs: NonNegative = 0
    quenchVariants: tuple[ContactSweepVariant, ...] = ()
    formationFadeMs: NonNegative = 0
    formationCommitMs: NonNegative = 0
    removalFadeMs: NonNegative = 0
    removalCommitMs: NonNegative = 0
    removalEasing: Literal["linear", "smoothstep"] = "linear"
    referenceRadiusFeet: Positive | None = None
    surfaceHeightScale: Positive = 1
    directedResponse: DirectedSpatialResponse | None = None
    interceptionComponents: str | None = None
    damageMaterials: FrozenMap[StudioBodyMaterialTrack] = Field(default_factory=lambda: MappingProxyType({}))
    contactMediaByEnergy: FrozenMap[tuple[StudioMediaTrack, ...]] = Field(default_factory=lambda: MappingProxyType({}))
    suppressionDirection: Point | None = None
    movementSpeedCellsPerSecond: Positive | None = None
    safeSideTint: RGBMediaTint | None = None
    contactMedia: Annotated[
        Mapping[Literal["ground_entry", "damage"], StudioMediaTrack],
        AfterValidator(MappingProxyType), PlainSerializer(dict, return_type=dict),
    ] = Field(default_factory=lambda: MappingProxyType({}))
    damageSweeps: Annotated[
        Mapping[Literal["contact", "radiated_heat"], ContactSweep],
        AfterValidator(MappingProxyType), PlainSerializer(dict, return_type=dict),
    ] = Field(default_factory=lambda: MappingProxyType({}))


    @model_validator(mode="after")
    def loop_window(self) -> SpatialMediaBinding:
        if self.loopCrossfadeMs >= self.holdFrames*1000/self.fps/2:
            raise ValueError("Loop crossfade must leave a nonoverlapping hold window")
        return self


class DepositMediaBinding(AuthoredRecord):
    """Authored material shapes registered to a physical deposition footprint."""

    radiusCells: Annotated[int, Field(ge=0)]
    variants: Annotated[tuple[SpatialMediaBinding, ...], Field(min_length=1)]


class ConstructionPhaseMedia(AuthoredRecord):
    """One original paired section bank; destruction requires its own fact."""

    application: tuple[Identifier, Identifier]
    intact: tuple[Identifier, Identifier]
    destruction: tuple[Identifier, Identifier]
    removal: tuple[Identifier, Identifier] | None = None


class ConstructionDirectionMedia(AuthoredRecord):
    tangent: tuple[float, float]
    centerlineOffsetCells: tuple[float, float]
    variants: Annotated[tuple[ConstructionPhaseMedia, ...], Field(min_length=1)]


class ConstructionSurfaceMedia(AuthoredRecord):
    """Original physical mesh/material sampled on admitted construction geometry."""
    material: Literal["force_membrane", "ice_shell"]
    components: Identifier
    motes: Identifier | None = None
    nativeUnitsPerCell: Positive
    verticalScale: Positive
    palette: Annotated[tuple[int, ...], Field(min_length=2)]
    domeOnly: bool = False
    applicationMs: Positive
    destructionMs: Positive
    removalMs: Positive


class ConstructionMediaBinding(AuthoredRecord):
    """Artwork for an admitted physical object, independently of its spell zone."""

    directions: tuple[ConstructionDirectionMedia, ...] = ()
    surface: ConstructionSurfaceMedia | None = None
    lengthFeet: Positive
    heightFeet: Positive
    pixelScale: Positive = 1
    formationCommitMs: NonNegative = 0
    removalDurationMs: Positive | None = None
    removalCommitMs: NonNegative = 0

    @model_validator(mode="after")
    def unique_headings(self) -> "ConstructionMediaBinding":
        if not self.directions and (self.surface is None or self.surface.domeOnly):
            raise ValueError('Construction requires native panel media')
        tangents = [row.tangent for row in self.directions]
        if len(set(tangents)) != len(tangents) or any(x*x+y*y <= 0 for x, y in tangents):
            raise ValueError('Construction banks require distinct nonzero tangents')
        has_removal = [v.removal is not None for d in self.directions for v in d.variants]
        if has_removal and (any(has_removal) != all(has_removal) or all(has_removal) != (self.removalDurationMs is not None)):
            raise ValueError('Construction retirement requires all banks and its source duration')
        return self


class EntityLifecyclePhase(AuthoredRecord):
    durationMs: Positive
    tracksByManifestation: FrozenMap[tuple[StudioMediaTrack, ...]]
    bodyFadeMs: tuple[NonNegative, Positive] | None = None

    @model_validator(mode="after")
    def finite_clocks(self) -> EntityLifecyclePhase:
        if self.bodyFadeMs is not None and not 0 <= self.bodyFadeMs[0] < self.bodyFadeMs[1] <= self.durationMs:
            raise ValueError("lifecycle body fade must fit its finite media")
        if set(self.tracksByManifestation) - {"natural", "fey_spirit", "fiend"}:
            raise ValueError("unknown lifecycle manifestation")
        for tracks in self.tracksByManifestation.values():
            for track in tracks:
                if track.loop or track.durationMs is None or not 0 <= track.startOffsetMs < self.durationMs:
                    raise ValueError("lifecycle media must have finite nonnegative clocks")
                if track.startOffsetMs + track.durationMs > self.durationMs:
                    raise ValueError("lifecycle track exceeds its phase")
        return self


@dataclass(frozen=True, slots=True)
class AnimationData:
    interruptions: InterruptionPresentation
    devices: Mapping[str, DeviceArt]
    device_wrecks: Mapping[str, DeviceArt]
    drafts: Mapping[str, StudioSpellDraft]
    attack_recipes: Mapping[str, AttackRecipe]
    shove_recipes: Mapping[str, ShoveRecipe]
    body_action_recipes: Mapping[str, BodyActionRecipe]
    body_action_bindings: Mapping[str, BodyActionBinding]
    condition_recipes: Mapping[str, ConditionRecipe]
    condition_media: Mapping[str, ConditionLayerMedia]
    projectile_assets: Mapping[str, AuthoredProjectileAsset]
    projectile_storage: Mapping[str, ProjectileStorage]
    media_root: Path
    rig: RigTables
    resources: Mapping[str, Path]
    root_rig: str
    rigs: Mapping[str, BodyRig]
    creature_rigs: Mapping[str, str]
    damage_context: DamageContext
    healing_context: HealingContext
    death_save_context: DeathSaveContext
    life_state_context: LifeStateContext
    death_context: DeathContext
    equipment_context: EquipmentTransitionContext
    movement_context: VoluntaryMovementContext
    movement_reaction_context: MovementReactionContext
    forced_movement_context: ForcedMovementContext
    forced_movement_profile: ForcedMovementProfile
    shove_feedback: Mapping[str, LifecycleFeedback]
    number_style: FloatingFeedbackStyle
    badge_style: FloatingFeedbackStyle
    dart_style: DartStyle
    bolt_style: BoltStyle
    vfx_source_hues: Mapping[str, float]
    # Unused action contexts remain exact source JSON until their family is ported.
    context_source_json: str
    world_animations: Mapping[str, PropAnimation]
    spatial_media: Mapping[str, SpatialMediaBinding]
    action_media_assets: Mapping[str, ActionMediaAsset | ParticleMediaAsset]
    body_release_media: Mapping[str, tuple[MovementMediaTrack, ...]]
    relocation_actions: frozenset[str] = frozenset()
    portals: Mapping[str, PortalArt | DoorwayArt] = field(default_factory=dict)
    blood_responses: Mapping[str, BloodResponse | None] = field(default_factory=dict)
    action_playback_rates: Mapping[str, float] = field(default_factory=dict)
    action_deliveries: Mapping[str, str] = field(default_factory=dict)
    movement_reference_speed_feet: float = 30
    deposit_media: Mapping[str, DepositMediaBinding] = field(default_factory=dict)
    concentration_media: Mapping[str, SpatialMediaBinding] = field(default_factory=dict)
    construction_media: Mapping[str, ConstructionMediaBinding] = field(default_factory=dict)
    body_materials: Mapping[SummonManifestation, BodyMaterial] = field(default_factory=dict)
    entity_lifecycle_media: Mapping[str, EntityLifecyclePhase] = field(default_factory=dict)
    item_attachments: Mapping[str, SpatialMediaBinding] = field(default_factory=dict)
    action_materials: Mapping[str, StudioBodyMaterialTrack] = field(default_factory=dict)
    action_intakes: Mapping[str, ObjectIntake] = field(default_factory=dict)
