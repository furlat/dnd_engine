"""Passive registered images shared by world and actor presentation."""

from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Literal, Mapping

from pydantic import BaseModel, ConfigDict, Field, PositiveFloat, PositiveInt, FiniteFloat, NonNegativeInt, TypeAdapter, model_validator


Vec3 = tuple[FiniteFloat, FiniteFloat, FiniteFloat]
Matrix3 = tuple[Vec3, Vec3, Vec3]
Matrix3x4 = tuple[tuple[FiniteFloat, FiniteFloat, FiniteFloat, FiniteFloat],
                   tuple[FiniteFloat, FiniteFloat, FiniteFloat, FiniteFloat],
                   tuple[FiniteFloat, FiniteFloat, FiniteFloat, FiniteFloat]]
_NonNegative = Annotated[FiniteFloat, Field(ge=0)]
_IdentityAffine: Matrix3x4 = ((1, 0, 0, 0), (0, 1, 0, 0), (0, 0, 1, 0))


def _invertible(matrix: Matrix3x4) -> bool:
    a, b, c = matrix
    return abs(a[0]*(b[1]*c[2]-b[2]*c[1]) - a[1]*(b[0]*c[2]-b[2]*c[0])
               + a[2]*(b[0]*c[1]-b[1]*c[0])) > 1e-12


class ReceivingMaterial(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True, allow_inf_nan=False)
    enabled: bool = True
    diffuseReflectanceLinear: tuple[_NonNegative, _NonNegative, _NonNegative] = (.18, .18, .18)
    preserveEmission: bool = False


class _Geometry(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True, allow_inf_nan=False)
    basis: Literal['camera_local', 'object_local']
    sourceToLocal: Matrix3x4 = _IdentityAffine

    @model_validator(mode='after')
    def invertible_registration(self):
        if not _invertible(self.sourceToLocal):
            raise ValueError('sourceToLocal must be invertible')
        return self


class PlaneGeometry(_Geometry):
    kind: Literal['plane'] = 'plane'
    normal: Vec3
    offset: FiniteFloat

    @model_validator(mode='after')
    def valid_normal(self):
        if not any(self.normal):
            raise ValueError('plane normal must be nonzero')
        return self


class MeshGeometry(_Geometry):
    kind: Literal['mesh'] = 'mesh'
    vertices: Annotated[tuple[Vec3, ...], Field(min_length=3)]
    triangles: Annotated[tuple[tuple[NonNegativeInt, NonNegativeInt, NonNegativeInt], ...], Field(min_length=1)]
    uvs: tuple[tuple[FiniteFloat, FiniteFloat], ...]
    faceIds: tuple[str, ...]
    sourcePolygons: dict[str, tuple[tuple[FiniteFloat, FiniteFloat], ...]] = Field(default_factory=dict)

    @model_validator(mode='after')
    def registered_faces(self):
        if len(self.uvs) != len(self.vertices) or len(self.faceIds) != len(self.triangles):
            raise ValueError('mesh UVs and face IDs must cover its vertices and triangles')
        if any(index >= len(self.vertices) for face in self.triangles for index in face):
            raise ValueError('mesh triangle references an absent vertex')
        if not set(self.sourcePolygons) <= set(self.faceIds):
            raise ValueError('source polygons must refer to registered faces')
        if any(len(polygon) < 3 for polygon in self.sourcePolygons.values()):
            raise ValueError('source face polygons require at least three vertices')
        return self


class EllipsoidKey(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True, allow_inf_nan=False)
    center: Vec3
    radii: tuple[PositiveFloat, PositiveFloat, PositiveFloat]


class EllipsoidGeometry(_Geometry):
    kind: Literal['ellipsoid'] = 'ellipsoid'
    keysByFrame: dict[NonNegativeInt, EllipsoidKey]
    contribution: Literal['near_surface', 'far_surface', 'near_quarter', 'far_quarter']
    colourShare: Literal['original', 'equal_transmittance_half']


class RestTransform(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True, allow_inf_nan=False)
    sourcePiece: str
    currentToRestByFrame: dict[NonNegativeInt, Matrix3x4]

    @model_validator(mode='after')
    def invertible_transforms(self):
        if any(not _invertible(matrix) for matrix in self.currentToRestByFrame.values()):
            raise ValueError('current-to-rest transforms must be invertible')
        return self


class RayDepthGeometry(_Geometry):
    kind: Literal['ray_depth'] = 'ray_depth'
    depthRange: tuple[FiniteFloat, FiniteFloat]
    encoding: Literal['rg16be_oct8_rgba8'] = 'rg16be_oct8_rgba8'
    pixelToRayOrigin: Matrix3
    rayDirection: Vec3
    restTransforms: tuple[RestTransform, ...] | None = None

    @model_validator(mode='after')
    def valid_ray(self):
        if self.depthRange[0] >= self.depthRange[1] or not any(self.rayDirection):
            raise ValueError('ray geometry needs an increasing depth range and nonzero direction')
        return self


MediaGeometry = Annotated[PlaneGeometry | MeshGeometry | EllipsoidGeometry | RayDepthGeometry, Field(discriminator='kind')]


class SourceClassPlane(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)
    kind: Literal['source_class'] = 'source_class'
    format: Literal['r8uint'] = 'r8uint'
    file: str


class RestPiecePlane(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)
    kind: Literal['rest_piece'] = 'rest_piece'
    format: Literal['r16uint'] = 'r16uint'
    file: str


OwnerPlane = Annotated[SourceClassPlane | RestPiecePlane, Field(discriminator='kind')]


class VisualEmitterKey(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True, allow_inf_nan=False)
    elapsedMs: _NonNegative
    position: Vec3
    colorLinear: tuple[_NonNegative, _NonNegative, _NonNegative]
    intensity: _NonNegative
    range: _NonNegative

    @model_validator(mode='after')
    def active_range(self):
        if self.intensity > 0 and self.range == 0:
            raise ValueError('An active emitter requires a positive range')
        return self


class VisualEmitter(BaseModel):
    """Cosmetic light in phase-local milliseconds and occurrence-local host units.

    Key positions are [x, height, z], already converted from source space;
    range uses host grid units. Apply the occurrence placement once, not the
    asset's source-to-host transform again. Intensity includes authored gains.
    """
    model_config = ConfigDict(extra='forbid', frozen=True)
    keys: Annotated[tuple[VisualEmitterKey, ...], Field(min_length=1)]
    interpolation: Literal['linear'] = 'linear'

    @model_validator(mode='after')
    def ordered_keys(self):
        if any(a.elapsedMs >= b.elapsedMs for a, b in zip(self.keys, self.keys[1:])):
            raise ValueError('emitter keys must have increasing phase times')
        return self


PixelRect = tuple[NonNegativeInt, NonNegativeInt, PositiveInt, PositiveInt]


class BytePlaneSource(BaseModel):
    """Derived lossless byte image registration; never browser-colour decoded."""
    model_config = ConfigDict(extra='forbid', frozen=True)
    encoding: Literal['raw_gzip'] = 'raw_gzip'
    width: PositiveInt
    height: PositiveInt
    channels: Literal[1, 2, 4]


class ImageRegionSource(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    path: str
    rect: PixelRect


class ImageSampleMapping(BaseModel):
    """Frame-local source index to data index; atlas origins are not pivots."""
    model_config = ConfigDict(extra='forbid', frozen=True, allow_inf_nan=False)
    scale: tuple[PositiveFloat, PositiveFloat] = (1, 1)
    offset: tuple[FiniteFloat, FiniteFloat] = (0, 0)
    rounding: Literal['floor'] = 'floor'
    pixel_center: tuple[FiniteFloat, FiniteFloat] = (.5, .5)
    # A padded colour canvas can map outside its data crop. Never clamp such
    # indices to an edge sample; absence of data is distinct from colour alpha.
    outside: Literal['absent'] = 'absent'


class NormalSampleSource(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True, allow_inf_nan=False)
    region: ImageRegionSource
    encoding: Literal['oct8_ba', 'oct8_rg', 'xyz8_rgb']
    sampling: ImageSampleMapping = Field(default_factory=ImageSampleMapping)
    # Effective packet-normal -> local, not an export transform already baked in.
    normalToLocal: Matrix3


_Byte = Annotated[int, Field(ge=0, le=255)]


class SourceRGBABounds(BaseModel):
    """Inclusive straight source bytes, before resampling or material treatment."""
    model_config = ConfigDict(extra='forbid', frozen=True)
    minimum: tuple[_Byte, _Byte, _Byte, _Byte]
    maximum: tuple[_Byte, _Byte, _Byte, _Byte]

    @model_validator(mode='after')
    def ordered_bounds(self):
        if any(low > high for low, high in zip(self.minimum, self.maximum)):
            raise ValueError('source RGBA minimum exceeds maximum')
        return self


class SurfaceMaskSource(BaseModel):
    """Integer evidence/role labels; their values are not opacity."""
    model_config = ConfigDict(extra='forbid', frozen=True)
    region: ImageRegionSource
    encoding: Literal['r8uint', 'r16uint', 'rgb8uint'] = 'r8uint'
    storage: Literal['png', 'raw'] = 'png'
    byte_order: Literal['little', 'big'] = 'little'
    channel: Literal['r', 'g', 'b', 'a'] = 'r'
    sampling: ImageSampleMapping = Field(default_factory=ImageSampleMapping)
    labels: dict[NonNegativeInt, str] = Field(default_factory=dict)


class WholeSurfaceSelection(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)
    kind: Literal['whole'] = 'whole'


class RGBASurfaceSelection(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)
    kind: Literal['source_rgba'] = 'source_rgba'
    bounds: SourceRGBABounds


class MaskSurfaceSelection(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)
    kind: Literal['mask'] = 'mask'
    mask: SurfaceMaskSource
    values: Annotated[tuple[NonNegativeInt, ...], Field(min_length=1)]


class SupportSurfaceReceiver(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True, allow_inf_nan=False)
    kind: Literal['support'] = 'support'
    height_steps: FiniteFloat = 0


class ResourceSurfaceReceiver(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)
    kind: Literal['resource'] = 'resource'
    resource_id: str


SurfaceReceiverSource = Annotated[SupportSurfaceReceiver | ResourceSurfaceReceiver,
                                 Field(discriminator='kind')]


class SurfaceSampleSource(BaseModel):
    """One calibrated surface; source layers may select distinct receivers."""
    model_config = ConfigDict(extra='forbid', frozen=True, allow_inf_nan=False)
    geometry: MediaGeometry | None = None
    geometry_region: ImageRegionSource | None = None
    geometry_sampling: ImageSampleMapping | None = None
    normal: NormalSampleSource | None = None
    receiving_geometry: PlaneGeometry | MeshGeometry | None = None
    support: SurfaceMaskSource | None = None
    qualification: str | None = None

    @model_validator(mode='after')
    def registered_samples(self):
        if self.geometry_region is not None and (self.geometry is None or self.geometry.kind != 'ray_depth'):
            raise ValueError('sampled image geometry requires ray-depth calibration')
        if self.geometry_sampling is not None and self.geometry_region is None:
            raise ValueError('geometry sampling needs its registered region')
        return self


class SurfaceRoleSource(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)
    role: Literal['solid', 'ground_shadow', 'translucent', 'surface_paint',
                  'ground_contact', 'cloth', 'emissive', 'occlusion']
    source_label: str | None = None
    selection: Annotated[WholeSurfaceSelection | RGBASurfaceSelection | MaskSurfaceSelection,
                         Field(discriminator='kind')]
    receiver: SurfaceReceiverSource | None = None
    # A supplied role receiver, e.g. furnace shadow at H=0, may differ from body.
    surface: SurfaceSampleSource | None = None


class SurfaceCompanionSource(SurfaceSampleSource):
    """Passive companion fields, shared by a static image and an actual frame."""
    component_owner: SurfaceMaskSource | None = None
    roles: tuple[SurfaceRoleSource, ...] = ()
    receiver: SurfaceReceiverSource | None = None


@dataclass(frozen=True, slots=True)
class ImageRegion:
    """One untrimmed source cell within a packed raster page."""

    path: Path
    rect: tuple[int, int, int, int]


class ImageResourceSource(SurfaceCompanionSource):
    """Unscaled pixel registration, decoded without touching the raster."""

    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)
    path: str
    native_size: tuple[PositiveInt, PositiveInt]
    pivot: tuple[FiniteFloat, FiniteFloat]
    scale: PositiveFloat
    rect: PixelRect | None = None
    receiving: ReceivingMaterial = Field(default_factory=ReceivingMaterial)

    @model_validator(mode="after")
    def untrimmed_region(self) -> "ImageResourceSource":
        if self.rect is not None and self.rect[2:] != self.native_size:
            raise ValueError("packed image rectangle must retain native_size")
        if self.geometry_region is not None:
            if self.geometry_region.rect[2:] != self.native_size and self.geometry_sampling is None:
                raise ValueError('independent geometry grid needs an explicit colour-to-data sampling map')
        return self


_IMAGE_RESOURCES = TypeAdapter(dict[str, ImageResourceSource])


@dataclass(frozen=True, slots=True)
class AssetSpec:
    __pydantic_config__ = ConfigDict(extra="forbid")

    asset_id: str
    path: Path
    native_size: tuple[int, int]
    pivot: tuple[float, float]
    scale: float
    rect: tuple[int, int, int, int] | None = None


def image_resources(rows: Mapping[str, object], root: Path) -> dict[str, AssetSpec]:
    """Read registration values without opening or auditing image files."""
    parsed = _IMAGE_RESOURCES.validate_python(rows)
    return {identity: AssetSpec(identity, root / row.path, row.native_size, row.pivot, row.scale, row.rect)
            for identity, row in parsed.items()}
