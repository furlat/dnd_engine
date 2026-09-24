"""Authored device bodies and retained emission contacts, independent of spells."""

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from types import MappingProxyType
from typing import Annotated, Literal, Mapping

from pydantic import BaseModel, ConfigDict, Field, FiniteFloat, PositiveFloat, PositiveInt, NonNegativeInt, model_validator

DeviceFacing = Literal["E", "SE", "S", "SW", "W", "NW", "N", "NE"]


class _DeviceSource(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)


class DevicePitchSource(_DeviceSource):
    pitchDegrees: FiniteFloat
    sheets: Annotated[tuple[str, ...], Field(min_length=4, max_length=4)]
    muzzlePixels: Annotated[
        tuple[tuple[tuple[tuple[FiniteFloat, FiniteFloat], ...], ...], ...],
        Field(min_length=4, max_length=4)]
    forwardScreen: Annotated[tuple[tuple[tuple[FiniteFloat, FiniteFloat], ...], ...],
                             Field(min_length=4, max_length=4)]
    muzzleHeightStepsByRow: tuple[FiniteFloat, ...]


class DeviceDestructionPitchSource(_DeviceSource):
    pitchDegrees: FiniteFloat
    sheets: Annotated[tuple[str, ...], Field(min_length=4, max_length=4)]


class DeviceDestructionSource(_DeviceSource):
    fps: PositiveFloat
    frameCount: PositiveInt
    pitchBanks: Annotated[tuple[DeviceDestructionPitchSource, ...], Field(min_length=1)]
    wreckItemId: str
    wreckSheets: Annotated[tuple[str, ...], Field(min_length=4, max_length=4)]


class DeviceArtSource(_DeviceSource):
    cell: tuple[PositiveInt, PositiveInt]
    anchor: tuple[FiniteFloat, FiniteFloat]
    rows: Annotated[tuple[DeviceFacing, ...], Field(min_length=1)]
    fps: PositiveFloat
    releaseFrame: NonNegativeInt
    frameCount: PositiveInt
    scale: PositiveFloat
    operatorRecipe: str
    launchPitchDegrees: FiniteFloat
    controlDistanceFraction: Annotated[float, Field(gt=0, le=1)]
    pitchBanks: Annotated[tuple[DevicePitchSource, ...], Field(min_length=1)]
    destruction: DeviceDestructionSource | None = None

    @model_validator(mode="after")
    def frame_contacts(self) -> "DeviceArtSource":
        if self.releaseFrame >= self.frameCount:
            raise ValueError("releaseFrame must index the device frames")
        for bank in self.pitchBanks:
            if len(bank.muzzleHeightStepsByRow) != len(self.rows):
                raise ValueError("muzzle heights must match facing rows")
            for camera, vectors in zip(bank.muzzlePixels, bank.forwardScreen):
                if len(camera) != len(self.rows) or len(vectors) != len(self.rows):
                    raise ValueError("muzzle and forward contacts must match facing rows")
                if any(len(frames) != self.frameCount for frames in camera):
                    raise ValueError("muzzle contacts must match the device frames")
        return self


class DeviceDocument(_DeviceSource):
    schema_name: Literal["dnd.spellDevices"] = Field(alias="schema")
    version: Literal[1]
    bindings: dict[str, str]
    devices: dict[str, DeviceArtSource]


@dataclass(frozen=True, slots=True)
class DevicePitch:
    degrees: float
    sheets: tuple[Path, ...]
    muzzle_pixels: tuple[tuple[tuple[tuple[float, float], ...], ...], ...]
    forward_screen: tuple[tuple[tuple[float, float], ...], ...]
    muzzle_heights: tuple[float, ...]


@dataclass(frozen=True, slots=True)
class DeviceDestruction:
    fps: float
    frame_count: int
    pitch_banks: Mapping[float, tuple[Path, ...]]
    wreck_item_id: str
    wreck_sheets: tuple[Path, ...]


@dataclass(frozen=True, slots=True)
class DeviceArt:
    identity: str
    cell: tuple[int, int]
    anchor: tuple[float, float]
    rows: tuple[DeviceFacing, ...]
    fps: float
    release_frame: int
    frame_count: int
    scale: float
    operator_recipe: str
    launch_pitch: float
    control_distance_fraction: float
    banks: tuple[DevicePitch, ...]
    destruction: DeviceDestruction | None = None


@dataclass(frozen=True, slots=True)
class DeviceEmission:
    """A historical placed object; operator identity remains on CastInput."""

    item_uuid: str
    grid: tuple[float, float]
    elevation_steps: float
    facing: DeviceFacing
    art: DeviceArt
    bank: DevicePitch


@lru_cache(maxsize=1)
def load_device_art() -> Mapping[str, DeviceArt]:
    """Read the small explicit catalog once; raster loading stays demand-driven."""
    root = Path(__file__).resolve().parent
    document = DeviceDocument.model_validate_json((root / "data/spell_devices.json").read_text())
    bodies = {}
    for identity, row in document.devices.items():
        broken = row.destruction
        destruction = None if broken is None else DeviceDestruction(
            broken.fps, broken.frameCount,
            MappingProxyType({bank.pitchDegrees: tuple(root / "assets" / path for path in bank.sheets)
                              for bank in broken.pitchBanks}),
            broken.wreckItemId, tuple(root / "assets" / path for path in broken.wreckSheets),
        )
        banks = tuple(DevicePitch(bank.pitchDegrees,
            tuple(root / "assets" / path for path in bank.sheets), bank.muzzlePixels,
            bank.forwardScreen, bank.muzzleHeightStepsByRow) for bank in row.pitchBanks)
        bodies[identity] = DeviceArt(identity, row.cell, row.anchor, row.rows, row.fps,
            row.releaseFrame, row.frameCount, row.scale, row.operatorRecipe, row.launchPitchDegrees,
            row.controlDistanceFraction, banks, destruction)
    return MappingProxyType({item: bodies[body] for item, body in document.bindings.items()})


@lru_cache(maxsize=1)
def load_device_wrecks() -> Mapping[str, DeviceArt]:
    """Static remnant bodies share the intact body's scale, pivot and yaw rows."""
    return MappingProxyType({art.destruction.wreck_item_id: art for art in load_device_art().values()
                             if art.destruction is not None})


def device_bank(art: DeviceArt) -> DevicePitch:
    return min(art.banks, key=lambda bank: abs(bank.degrees - art.launch_pitch))


def device_frame(emission: DeviceEmission, elapsed_ms: float, release_ms: float) -> int:
    """Seekable one-shot body phase; the spell keeps its own delivery clock."""
    start = release_ms - emission.art.release_frame * 1000 / emission.art.fps
    return min(emission.art.frame_count - 1, max(0, int((elapsed_ms - start) * emission.art.fps / 1000)))


def device_muzzle_offset(emission: DeviceEmission, quadrant: int, frame: int | None = None) -> tuple[float, float]:
    """Measured muzzle in unscaled screen pixels, relative to the placed support."""
    art = emission.art
    point = emission.bank.muzzle_pixels[quadrant][art.rows.index(emission.facing)][
        art.release_frame if frame is None else frame]
    return ((point[0] - art.anchor[0]) * art.scale, (point[1] - art.anchor[1]) * art.scale)
