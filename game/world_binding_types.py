"""Passive, shared admission schema for the world presentation document."""

from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, FiniteFloat, PositiveFloat, PositiveInt, NonNegativeInt, model_validator
from dnd.types.residues import ResidueEllipse
from game.asset_types import ImageResourceSource
from game.animation_types import Facing8, SpatialMediaBinding, ConstructionMediaBinding, DepositMediaBinding


class _PropSource(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)


class MechanismProjectileSource(_PropSource):
    frames_by_pose: dict[str, Annotated[tuple[str, ...], Field(min_length=1)]]
    tip_offsets_by_pose: dict[str, tuple[tuple[FiniteFloat, FiniteFloat], ...]]
    muzzle_offsets_by_pose: dict[str, tuple[FiniteFloat, FiniteFloat]]
    muzzle_height_steps: FiniteFloat
    speed_tiles_per_second: PositiveFloat

    @model_validator(mode="after")
    def registered_frames(self) -> "MechanismProjectileSource":
        if set(self.frames_by_pose) != set(self.tip_offsets_by_pose) or set(self.frames_by_pose) != set(self.muzzle_offsets_by_pose):
            raise ValueError("projectile contacts must cover its poses")
        if any(len(frames) != len(self.tip_offsets_by_pose[pose]) for pose, frames in self.frames_by_pose.items()):
            raise ValueError("projectile tips must cover its frames")
        return self


class SaveHopSource(_PropSource):
    effect_id: str
    body_clip: str
    duration_ms: PositiveFloat
    height_px: PositiveFloat


class PropDepthSource(_PropSource):
    asset_id: str
    cell: tuple[PositiveInt, PositiveInt]
    rows_by_pose: dict[str, NonNegativeInt]
    depth_range: tuple[FiniteFloat, FiniteFloat]
    pixels_per_unit_by_pose: dict[str, PositiveFloat]


class TetherSource(_PropSource):
    frames_by_facing: dict[Facing8, Annotated[tuple[str, ...], Field(min_length=1)]]
    endpoints_by_facing: dict[Facing8, tuple[tuple[FiniteFloat, FiniteFloat], tuple[FiniteFloat, FiniteFloat]]]
    fps: PositiveFloat


class PropAnimationSource(_PropSource):
    frames_by_pose: Annotated[dict[str, Annotated[tuple[str, ...], Field(min_length=1)]], Field(min_length=1)]
    fps: PositiveInt
    state_frames: dict[str, NonNegativeInt]
    default_frame: NonNegativeInt = 0
    placement: Literal["cell", "area", "anchor"] = "cell"
    origin_offset: tuple[FiniteFloat, FiniteFloat] = (0, 0)
    creation_start_frame: NonNegativeInt | None = None
    footprint_tiles: tuple[PositiveInt, PositiveInt] | None = None
    activation_frames: tuple[NonNegativeInt, ...] = ()
    contact_frame: NonNegativeInt | None = None
    transition_frames: dict[str, tuple[NonNegativeInt, ...]] = Field(default_factory=dict)
    projectile: MechanismProjectileSource | None = None
    depth: Literal["ground", "world"] = "ground"
    successful_save_hop: SaveHopSource | None = None
    actor_depth: PropDepthSource | None = None
    # Adjacent world-catalog media share the authored object's source row.
    tether: TetherSource | None = None
    residue_overlays: dict[str, dict[str, tuple[str, ...]]] = Field(default_factory=dict)

    @model_validator(mode="after")
    def frame_markers(self) -> "PropAnimationSource":
        markers = (self.default_frame, self.creation_start_frame, self.contact_frame,
                   *self.state_frames.values(), *self.activation_frames,
                   *(frame for frames in self.transition_frames.values() for frame in frames))
        limit = min(map(len, self.frames_by_pose.values()))
        if any(frame is not None and frame >= limit for frame in markers):
            raise ValueError("prop frame markers must index each pose's frames")
        return self


class _WorldSource(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)


class ImageAnimationSource(_WorldSource):
    frames: Annotated[tuple[str, ...], Field(min_length=1)]
    fps: PositiveInt


class WaterSource(_WorldSource):
    mask: str
    ripple: str
    normal: str
    shallowColor: tuple[FiniteFloat, FiniteFloat, FiniteFloat, FiniteFloat]
    deepColor: tuple[FiniteFloat, FiniteFloat, FiniteFloat, FiniteFloat]
    tint: tuple[FiniteFloat, FiniteFloat, FiniteFloat, FiniteFloat]
    depthBlendStrength: FiniteFloat
    uvScale: PositiveFloat
    detailPan: tuple[FiniteFloat, FiniteFloat]
    detailInfluence: FiniteFloat
    ripplePan: tuple[FiniteFloat, FiniteFloat]
    rippleTilingMultiplier: PositiveFloat
    rippleAmount: FiniteFloat
    uvWobbleAmount: FiniteFloat
    normalPanA: tuple[FiniteFloat, FiniteFloat]
    normalPanB: tuple[FiniteFloat, FiniteFloat]
    normalTilingMultiplier: PositiveFloat
    normalScale: FiniteFloat
    sheenStrength: FiniteFloat
    sheenSharpness: PositiveFloat
    overallAlpha: Annotated[float, Field(ge=0, le=1)]
    alphaDepthStrength: FiniteFloat
    alphaCutoff: Annotated[float, Field(ge=0, le=1)]
    premultiplyOutput: bool
    blend: Literal["one_one_minus_src_alpha"]


class AssetDocument(_WorldSource):
    schema_version: Literal[1]
    resources: dict[str, ImageResourceSource]
    animations: dict[str, ImageAnimationSource]
    water: WaterSource


class PropBindingSource(_WorldSource):
    body_by_pose: dict[str, str]
    lit_animation: str | None
    state_field: Literal["is_open", "is_engaged"] | None = None
    active_body_by_pose: dict[str, str] | None = None
    transition: PropAnimationSource | None = None


class TerrainCliffSource(_WorldSource):
    role: Literal["cliff"]
    rise_steps: PositiveInt
    bed_material: str
    upper_support_offset: tuple[int, int]
    straight: dict[str, str]
    corner: dict[str, str]
    corner_faces: dict[str, tuple[Literal["east", "south", "west", "north"], Literal["east", "south", "west", "north"]]]


class TerrainStairSource(_WorldSource):
    role: Literal["stairs"]
    rise_steps: PositiveInt
    support_offsets: tuple[tuple[int, int, int], ...]
    poses: dict[str, str]
    contacts_px: dict[str, tuple[tuple[FiniteFloat, FiniteFloat], ...]]


class TreatmentSource(_WorldSource):
    id: str
    rgb: tuple[FiniteFloat, FiniteFloat, FiniteFloat]


class ResidueSurfaceSource(_WorldSource):
    floor_atlas: str
    wall_atlas: str
    floor_opacity: Annotated[float, Field(ge=0, le=1)]
    wall_opacity: Annotated[float, Field(ge=0, le=1)]


class WallFaceSource(_WorldSource):
    origin: tuple[FiniteFloat, FiniteFloat]
    across: tuple[FiniteFloat, FiniteFloat]
    down: tuple[FiniteFloat, FiniteFloat]
    reverse: bool = False


class WallFacesSource(_WorldSource):
    profiles: dict[str, dict[str, tuple[WallFaceSource, ...]]] = Field(default_factory=dict)
    assets: dict[str, str] = Field(default_factory=dict)


class LiquidSurfaceSource(_WorldSource):
    asset_id: str
    ellipse: ResidueEllipse
    opacity: Annotated[float, Field(ge=0, le=1)]


class WorldBindingsSource(_WorldSource):
    schema_version: Literal[1]
    terrain: dict[str, dict[str, str] | str]
    terrain_cliff: TerrainCliffSource
    terrain_stairs: TerrainStairSource
    stone_wall_straight: dict[str, str]
    stone_wall_corner: dict[str, str]
    wood_wall_straight: dict[str, str]
    wood_wall_corner: dict[str, str]
    stone_door_frame: dict[str, str]
    wood_door_closed: dict[str, str]
    wood_door_open: dict[str, str]
    props: dict[str, PropBindingSource]
    treatments: dict[str, TreatmentSource]
    spatial_effects: dict[str, PropAnimationSource] = Field(default_factory=dict)
    residue_wall_faces: WallFacesSource = Field(default_factory=WallFacesSource)
    residue_particles: dict[str, str] = Field(default_factory=dict)
    residue_ground: dict[str, dict[str, str]] = Field(default_factory=dict)
    residue_surfaces: dict[str, ResidueSurfaceSource] = Field(default_factory=dict)
    liquid_surfaces: dict[str, LiquidSurfaceSource] = Field(default_factory=dict)
    spatial_media: dict[str, SpatialMediaBinding] = Field(default_factory=dict)
    concentration_media: dict[str, SpatialMediaBinding] = Field(default_factory=dict)
    construction_media: dict[str, ConstructionMediaBinding] = Field(default_factory=dict)
    deposit_media: dict[str, DepositMediaBinding] = Field(default_factory=dict)


