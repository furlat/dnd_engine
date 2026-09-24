"""Authored environment atlases; native state selects the finite bank."""

from bisect import bisect_right
from dataclasses import dataclass, field
from functools import lru_cache
import json
from pathlib import Path
from types import MappingProxyType
from typing import Annotated, Literal, Mapping

from pydantic import BaseModel, ConfigDict, Field, FiniteFloat, PositiveFloat, PositiveInt, NonNegativeFloat, NonNegativeInt, model_validator

from game.animation_types import PropDepth
from game.asset_types import ImageRegion, ImageRegionSource


class _EnvironmentSource(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)


class EnvironmentDepthSource(_EnvironmentSource):
    path: str | None = None
    cell: tuple[PositiveInt, PositiveInt]
    depth_range: tuple[FiniteFloat, FiniteFloat]
    pixels_per_unit_by_pose: dict[str, PositiveFloat]


class EnvironmentBankSource(_EnvironmentSource):
    path: str | None = None
    cell: tuple[PositiveInt, PositiveInt]
    ground_pivot: tuple[FiniteFloat, FiniteFloat]
    pivots_by_pose: dict[str, tuple[FiniteFloat, FiniteFloat]]
    rows: Annotated[tuple[str, ...], Field(min_length=1)]
    scale: PositiveFloat
    frame_count: PositiveInt
    fps: PositiveFloat | None = None
    sample_times_ms: tuple[NonNegativeFloat, ...] | None = None
    duration_ms: NonNegativeFloat
    ground_origins_by_pose: dict[str, tuple[FiniteFloat, FiniteFloat]] = Field(default_factory=dict)
    frame_path: str | None = None
    leaf_path: str | None = None
    actor_depth: EnvironmentDepthSource | None = None
    release_frame: NonNegativeInt | None = None
    state_change_frame: NonNegativeInt = 0
    frames_by_pose: dict[str, tuple[ImageRegionSource, ...]] = Field(default_factory=dict)
    depth_frames_by_pose: dict[str, tuple[ImageRegionSource, ...]] = Field(default_factory=dict)
    frame_regions_by_pose: dict[str, ImageRegionSource] = Field(default_factory=dict)

    @model_validator(mode="after")
    def sampled_frames(self) -> "EnvironmentBankSource":
        if self.path is None and not self.frames_by_pose:
            raise ValueError("bank needs a sheet or packed color frames")
        for label, poses, cell in (("color", self.frames_by_pose, self.cell),
                ("depth", self.depth_frames_by_pose, self.actor_depth.cell if self.actor_depth else None)):
            if not poses:
                continue
            if cell is None or set(poses) != set(self.rows):
                raise ValueError(f"{label} frames must match the bank pose registration")
            if any(len(frames) != self.frame_count for frames in poses.values()):
                raise ValueError(f"{label} packed frames must match frame_count")
            if any(region.rect[2:] != cell for frames in poses.values() for region in frames):
                raise ValueError(f"{label} packed rectangles must retain their source cell size")
        if self.actor_depth is not None and self.actor_depth.path is None and not self.depth_frames_by_pose:
            raise ValueError("actor depth needs a sheet or packed depth frames")
        if self.frame_regions_by_pose and (set(self.frame_regions_by_pose) != set(self.rows)
                or any(region.rect[2:] != self.cell for region in self.frame_regions_by_pose.values())):
            raise ValueError("static frame regions must match the bank poses and cell size")
        if self.sample_times_ms is None and self.fps is None:
            raise ValueError("bank needs sample times or fps")
        if self.sample_times_ms is not None:
            times = self.sample_times_ms
            if len(times) != self.frame_count or any(a >= b for a, b in zip(times, times[1:])):
                raise ValueError("sample times must be ordered and match the bank frames")
            if times[-1] > self.duration_ms:
                raise ValueError("sample times cannot outlast the bank duration")
        for marker in (self.release_frame, self.state_change_frame):
            if marker is not None and marker >= self.frame_count:
                raise ValueError("bank frame marker must index its frames")
        if set(self.rows) != set(self.pivots_by_pose):
            raise ValueError("bank pivots must cover its pose rows")
        return self


class EnvironmentDoorSource(_EnvironmentSource):
    openings: dict[str, str]
    destructions: dict[str, str]
    pose_offset: int
    frame_resource_by_pose: dict[str, str]


class EnvironmentTrapSource(_EnvironmentSource):
    intact: str
    state_frames: dict[str, NonNegativeInt]
    destructions: dict[str, str]


class EnvironmentWreckSource(_EnvironmentSource):
    source_item_id: str
    outcome: str | None = None


class EnvironmentPropSource(_EnvironmentSource):
    state_field: Literal["is_open"] | None = None
    intact: dict[str, str]
    destructions: dict[str, str]


class EnvironmentDocument(_EnvironmentSource):
    version: Literal[1]
    banks: dict[str, EnvironmentBankSource]
    doors: dict[str, EnvironmentDoorSource]
    traps: dict[str, EnvironmentTrapSource]
    wrecks: dict[str, EnvironmentWreckSource]
    props: dict[str, EnvironmentPropSource] = Field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class EnvironmentBank:
    identity: str
    path: Path | None
    cell: tuple[int, int]
    ground_pivot: tuple[float, float]
    pivots_by_pose: Mapping[str, tuple[float, float]]
    rows: tuple[str, ...]
    scale: float
    frame_count: int
    frame_times_ms: tuple[float, ...]
    duration_ms: float
    # Source geometry.projections ground_origin_px, independent of mounting pivots.
    ground_origins_by_pose: Mapping[str, tuple[float, float]]
    frame_path: Path | None = None
    leaf_path: Path | None = None
    depth_path: Path | None = None
    actor_depth: PropDepth | None = None
    release_frame: int | None = None
    state_change_frame: int = 0
    frames_by_pose: Mapping[str, tuple[ImageRegion, ...]] = field(default_factory=lambda: MappingProxyType({}))
    depth_frames_by_pose: Mapping[str, tuple[ImageRegion, ...]] = field(default_factory=lambda: MappingProxyType({}))
    frame_regions_by_pose: Mapping[str, ImageRegion] = field(default_factory=lambda: MappingProxyType({}))


@dataclass(frozen=True, slots=True)
class EnvironmentDoorArt:
    openings: Mapping[str, EnvironmentBank]
    destructions: Mapping[str, EnvironmentBank]
    pose_offset: int
    frame_resource_by_pose: Mapping[str, str]


@dataclass(frozen=True, slots=True)
class EnvironmentTrapArt:
    intact: EnvironmentBank
    state_frames: Mapping[str, int]
    destructions: Mapping[str, EnvironmentBank]


@dataclass(frozen=True, slots=True)
class EnvironmentPropArt:
    state_field: Literal["is_open"] | None
    intact: Mapping[str, EnvironmentBank]
    destructions: Mapping[str, EnvironmentBank]


@dataclass(frozen=True, slots=True)
class EnvironmentWreckArt:
    source_item_id: str
    outcome: str | None


@dataclass(frozen=True, slots=True)
class EnvironmentArt:
    banks: Mapping[str, EnvironmentBank]
    doors: Mapping[str, EnvironmentDoorArt]
    traps: Mapping[str, EnvironmentTrapArt]
    wrecks: Mapping[str, EnvironmentWreckArt]
    props: Mapping[str, EnvironmentPropArt]


def prop_state_key(art: EnvironmentPropArt, is_open: bool | None) -> str | None:
    if art.state_field is None:
        return "default"
    return None if is_open is None else str(is_open).lower()


def sample_environment_frame(bank: EnvironmentBank, elapsed_ms: float,
                             *, reverse: bool = False) -> int:
    """Seek authored frame times, holding the exact final pose indefinitely."""
    index = max(0, min(bank.frame_count - 1,
                       bisect_right(bank.frame_times_ms, elapsed_ms) - 1))
    return bank.frame_count - 1 - index if reverse else index


def select_environment_destruction(
    art: EnvironmentArt, item_id: str, *, door_open: bool | None = None,
    swing: str | None = None, mechanism_state: str | None = None,
    outcome: str | None = None,
) -> EnvironmentBank | None:
    """Select only an explicitly delivered entry from recorded native state."""
    wreck = art.wrecks.get(item_id)
    if wreck is not None:
        item_id, outcome = wreck.source_item_id, wreck.outcome
    trap = art.traps.get(item_id)
    if trap is not None:
        return trap.destructions.get(mechanism_state) if mechanism_state is not None else None
    prop = art.props.get(item_id)
    if prop is not None:
        state = prop_state_key(prop, door_open)
        return prop.destructions.get(state) if state is not None else None
    door = art.doors.get(item_id)
    if door is None or door_open is None or outcome is None:
        return None
    if door_open and swing is None:
        return None
    entry = f"open.{swing}" if door_open else "closed"
    return door.destructions.get(f"{entry}.{outcome}")


def environment_art_from_document(document: Mapping[str, object], asset_root: Path) -> EnvironmentArt:
    """Decode explicit resources once; no raster reads or source verification."""
    source = EnvironmentDocument.model_validate(document)
    banks = {}
    for identity, row in source.banks.items():
        if row.sample_times_ms is not None:
            times = row.sample_times_ms
        else:
            assert row.fps is not None
            times = tuple(index * 1000 / row.fps for index in range(row.frame_count))
        depth = row.actor_depth
        registration = None if depth is None else PropDepth(
            identity + ".depth", depth.cell,
            MappingProxyType({pose: index for index, pose in enumerate(row.rows)}),
            depth.depth_range, MappingProxyType(depth.pixels_per_unit_by_pose),
        )
        banks[identity] = EnvironmentBank(
            identity, asset_root / row.path if row.path is not None else None, row.cell, row.ground_pivot,
            MappingProxyType(row.pivots_by_pose), row.rows, row.scale, row.frame_count,
            times, row.duration_ms,
            MappingProxyType({pose: row.ground_origins_by_pose.get(pose, row.ground_pivot) for pose in row.rows}),
            asset_root / row.frame_path if row.frame_path is not None else None,
            asset_root / row.leaf_path if row.leaf_path is not None else None,
            asset_root / depth.path if depth is not None and depth.path is not None else None, registration,
            row.release_frame, row.state_change_frame,
            MappingProxyType({pose: tuple(ImageRegion(asset_root / region.path, region.rect) for region in frames)
                              for pose, frames in row.frames_by_pose.items()}),
            MappingProxyType({pose: tuple(ImageRegion(asset_root / region.path, region.rect) for region in frames)
                              for pose, frames in row.depth_frames_by_pose.items()}),
            MappingProxyType({pose: ImageRegion(asset_root / region.path, region.rect)
                              for pose, region in row.frame_regions_by_pose.items()}),
        )
    doors = {identity: EnvironmentDoorArt(
        MappingProxyType({mode: banks[key] for mode, key in row.openings.items()}),
        MappingProxyType({mode: banks[key] for mode, key in row.destructions.items()}),
        row.pose_offset, MappingProxyType(row.frame_resource_by_pose),
    ) for identity, row in source.doors.items()}
    traps = {identity: EnvironmentTrapArt(banks[row.intact], MappingProxyType(row.state_frames),
        MappingProxyType({mode: banks[key] for mode, key in row.destructions.items()}),
    ) for identity, row in source.traps.items()}
    for identity, trap in traps.items():
        if any(frame >= trap.intact.frame_count for frame in trap.state_frames.values()):
            raise ValueError(f"{identity}: state frames must index its intact bank")
    wrecks = {identity: EnvironmentWreckArt(row.source_item_id, row.outcome)
              for identity, row in source.wrecks.items()}
    props = {identity: EnvironmentPropArt(row.state_field,
        MappingProxyType({state: banks[key] for state, key in row.intact.items()}),
        MappingProxyType({state: banks[key] for state, key in row.destructions.items()}),
    ) for identity, row in source.props.items()}
    return EnvironmentArt(MappingProxyType(banks), MappingProxyType(doors),
                          MappingProxyType(traps), MappingProxyType(wrecks), MappingProxyType(props))


@lru_cache(maxsize=1)
def load_environment_art() -> EnvironmentArt:
    root = Path(__file__).resolve().parent
    document = json.loads((root / "data/environment_art.json").read_text())
    return environment_art_from_document(document, root / "assets")
