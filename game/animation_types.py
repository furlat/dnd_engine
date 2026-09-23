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

from pydantic import (
    AfterValidator, BaseModel, ConfigDict, Field, JsonValue, PlainSerializer,
    field_serializer, model_validator,
)

from dnd.core.content.identities import ContentRef
from game.condition_types import ConditionBodyAnimation, ConditionRecipe
from game.condition_media import ConditionLayerMedia
from game.device_art import DeviceArt
from game.portal_art import PortalArt

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


class PaletteTreatment(AuthoredRecord):
    """Exact authored colors and optional source noise for isolated recoloring."""

    colors: Annotated[tuple[Color, ...], Field(min_length=1)]
    gamma: Positive = .65
    noiseSheet: Identifier | None = None
    untinted: bool = False


class StudioActorLayer(AuthoredRecord):
    id: Identifier
    slot: Literal["weaponGlow", "aura", "effect", "effect2", "effect3", "slash"]
    enabled: bool
    hidden: bool
    category: Identifier
    colors: LayerColors
    # Optional isolated, already-colored export; never recolor the actor body.
    sourceSheet: Identifier | None = None
    # Offline bake input for sourceSheet; runtime uses the already-colored sheet.
    palette: PaletteTreatment | None = None


class StudioEquipment(AuthoredRecord):
    kind: Literal["unchanged", "hidden", "melee", "ranged"]


class ChildAttackPose(AuthoredRecord):
    """Literal actor layers fitted to one existing rig/weapon/attack pose."""

    rigId: Identifier
    weaponCategory: Identifier
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
    color: Color
    palette: PaletteTreatment | None = None


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


class StudioMediaTrack(AuthoredRecord):
    """Finite authored media on the cast clock, independent of travel geometry."""

    id: Identifier
    assetId: Identifier
    assetPhase: Literal["cast", "travel", "impact"] = "impact"
    attachment: Literal["source_hand", "source_ground", "target_body", "target_ground", "area_ground",
                        "departure_ground", "arrival_ground"]
    startOffsetMs: float = 0
    fps: Positive | None = None
    durationMs: Positive | None = None
    loop: bool = False
    scale: Positive = 1
    scaleWithActor: bool = False
    alpha: Annotated[float, Field(ge=0, le=1)] = 1
    depth: Literal["world", "ground", "behind_body", "front_body"] = "world"
    orientation: Literal["authored", "target_vector"] = "authored"
    # Fixed-world orbit banks use an authored camera basis. Omission retains
    # facing-driven media such as directed projectiles and sprays.
    viewFacing: Facing8 | None = None
    onMiss: Literal["play", "omit"] = "play"
    worldOffsetsByFacing: FacingMap[Point] | None = None
    timeMap: tuple[MediaTimePoint, ...] = ()
    timeMapsByFacing: FacingMap[tuple[MediaTimePoint, ...]] | None = None
    bodyOffsetsByFacing: FacingMap[tuple[Point, ...]] | None = None
    # Source pixels from whole-effect origin to the baked attachment point.
    emissionPointByFacing: FacingMap[Point] | None = None


class StudioContact(AuthoredRecord):
    """Presentation arrival; outcomes still come solely from native events."""

    delayMs: NonNegative = 0
    speedTilesPerSecond: Positive | None = None
    cellsByFacing: FacingMap[FrozenMap[NonNegative]] | None = None

    @field_serializer("cellsByFacing")
    def serialize_cell_contacts(self, value: Mapping[Facing8, Mapping[str, float]] | None
                                ) -> dict[Facing8, dict[str, float]] | None:
        return None if value is None else {facing: dict(cells) for facing, cells in value.items()}


class StudioSpellDraft(AuthoredRecord):
    definitionRef: ContentRef
    elementColors: ElementColors
    cast: StudioCast
    projectile: StudioProjectile | None = None
    area: StudioArea | None = None
    damage: StudioDamage | None = None
    condition: StudioCondition | None = None
    media: tuple[StudioMediaTrack, ...] = ()
    contact: StudioContact | None = None
    childAttack: ChildAttackPresentation | None = None


class StudioDraftFile(AuthoredRecord):
    schema_: Literal["neuroclient.spellStudioDrafts", "dnd.spellStudioDrafts"] = Field(alias="schema")
    version: Literal[1, 2, 6]
    spells: tuple[StudioSpellDraft, ...]
    effectDrafts: FrozenMap[StudioSpellDraft] = Field(default_factory=dict)

    @model_validator(mode="after")
    def format_version(self) -> StudioDraftFile:
        supported = (6,) if self.schema_ == "neuroclient.spellStudioDrafts" else (1, 2)
        if self.version not in supported:
            raise ValueError(f"{self.schema_} requires version {supported}")
        return self


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


class PackedFootpoint(AuthoredRecord):
    """Aligned raw RGBA: big-endian uint16 X in RG and Y in BA, in local cells."""

    file: Identifier
    bounds: tuple[float, float]


class ProjectileFramePart(AuthoredRecord):
    """Lossless sparse packing in an asset's unchanged logical canvas."""

    file: Identifier
    rect: tuple[int, int, int, int]
    offset: tuple[int, int]
    footpoint: PackedFootpoint | None = None


class ProjectileFrameStorage(AuthoredRecord):
    layers: tuple[ProjectileFrameLayer, ...] = ()
    surfaceFrames: PackedSurfaceFrames | None = None


class PackedSurfaceFrames(AuthoredRecord):
    """Matched RGBA/XYZ/ownership packets; frame selection leaves source timing authored."""

    pattern: str | None = None
    frameIndices: tuple[int, ...]
    bounds: tuple[float, float]
    verticalScale: Positive
    blendModes: tuple[Literal["normal", "add"], ...] = ()
    componentsByFacing: FacingMap[tuple[PackedSurfaceComponent, ...]] | None = None
    positionScale: Positive = 1


class PackedSurfaceComponent(AuthoredRecord):
    """One ordered source component, registered to the whole effect origin."""

    pattern: str
    pivot: tuple[float, float]
    blendMode: Literal["normal", "add"]


class ProjectileStorage(AuthoredRecord):
    phases: FrozenMap[ProjectileFrameStorage]


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


PoseSockets = FrozenMap[FrozenMap[FacingMap[tuple[Point, ...]]]]


class BodyRig(AuthoredRecord):
    """Passive body layout/capabilities, shared by timing and pixel sampling."""

    cell_width: Annotated[int, Field(ge=1)]
    cell_height: Annotated[int, Field(ge=1)]
    origin_y_from_ground: float
    body_anchor: Point | None = None
    rest_pose_anchors: FrozenMap[FacingMap[Point]] = Field(default_factory=dict)
    # Socket / semantic clip / viewed facing / sampled frame, in full-cell pixels.
    pose_sockets: PoseSockets = Field(default_factory=dict)
    facing_rows: FacingMap[int]
    slot_order: tuple[str, ...]
    slot_categories: FrozenMap[tuple[str, ...]]
    clips: FrozenMap[BodyClip]

    @field_serializer("rest_pose_anchors")
    def serialize_rest_pose_anchors(self, value: Mapping[str, Mapping[Facing8, Point]]) -> dict[str, dict[Facing8, Point]]:
        return {pose: dict(points) for pose, points in value.items()}

    @field_serializer("pose_sockets")
    def serialize_pose_sockets(self, value: PoseSockets) -> dict[str, dict[str, dict[Facing8, tuple[Point, ...]]]]:
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
        for clips in self.pose_sockets.values():
            for name, rows in clips.items():
                if name not in self.clips or set(rows) != facings:
                    raise ValueError("pose sockets require an existing clip and all eight facings")
                if any(len(points) != self.clips[name].frames for points in rows.values()):
                    raise ValueError("pose sockets require one point per body frame")
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
    color: Color
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
    color: Color


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


class MovementPresentation(AuthoredRecord):
    schema_: Literal["dnd.movementPresentation"] = Field(alias="schema")
    version: Literal[1]
    referenceSpeedFeet: Positive
    actionPlaybackRates: FrozenMap[Positive]
    walkMedia: tuple[MovementMediaTrack, ...]
    jumpMedia: tuple[MovementMediaTrack, ...]


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
    # Current gear uses stable item identities; imported Studio refs remain readable.
    sourceItemIds: tuple[str, ...] | None = None


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


class AttackProfileFile(AuthoredRecord):
    """Local shared profiles in the original NeuroStudio variant vocabulary."""

    behaviors: tuple[Identifier, ...]
    variants: tuple[AttackVariant, ...]


class ActionFeedback(AuthoredRecord):
    text: Identifier
    color: Color


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


class SpatialMediaLayer(AuthoredRecord):
    """One registered layer around the received area's occupants."""
    assetId: Identifier
    applicationAssetId: Identifier | None = None
    side: Literal["center", "rear", "front"] = "center"
    removalAssetId: Identifier | None = None
    suppressionAssetId: Identifier | None = None
    composition: Literal["legacy", "floor", "volume", "clump"] = "legacy"
    offsetCells: tuple[float, float] = (0, 0)
    delayMs: NonNegative = 0


class SpatialMediaBinding(AuthoredRecord):
    """A maintained window in existing finite media; native observation owns existence."""

    layers: Annotated[tuple[SpatialMediaLayer, ...], Field(min_length=1)]
    assetPhase: Literal["cast", "travel", "impact"] = "impact"
    holdStartFrame: Annotated[int, Field(ge=0)]
    holdFrames: Annotated[int, Field(ge=1)]
    fps: Positive
    scale: Positive
    removalFadeMs: NonNegative = 0
    removalEasing: Literal["linear", "smoothstep"] = "linear"
    referenceRadiusFeet: Positive | None = None
    surfaceHeightScale: Positive = 1
    suppressionDirection: Point | None = None
    movementSpeedCellsPerSecond: Positive | None = None
    contactMedia: Annotated[
        Mapping[Literal["ground_entry", "damage"], StudioMediaTrack],
        AfterValidator(MappingProxyType), PlainSerializer(dict, return_type=dict),
    ] = Field(default_factory=lambda: MappingProxyType({}))


class DepositMediaBinding(AuthoredRecord):
    """Authored material shapes registered to a physical deposition footprint."""

    radiusCells: Annotated[int, Field(ge=0)]
    variants: Annotated[tuple[SpatialMediaBinding, ...], Field(min_length=1)]


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
    portals: Mapping[str, PortalArt] = field(default_factory=dict)
    blood_responses: Mapping[str, BloodResponse | None] = field(default_factory=dict)
    action_playback_rates: Mapping[str, float] = field(default_factory=dict)
    action_deliveries: Mapping[str, str] = field(default_factory=dict)
    movement_reference_speed_feet: float = 30
    deposit_media: Mapping[str, DepositMediaBinding] = field(default_factory=dict)
