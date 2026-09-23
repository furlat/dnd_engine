"""Authored device bodies and retained emission contacts, independent of spells."""

from dataclasses import dataclass
from functools import lru_cache
import json
from pathlib import Path
from types import MappingProxyType
from typing import Literal, Mapping

DeviceFacing = Literal["E", "SE", "S", "SW", "W", "NW", "N", "NE"]


@dataclass(frozen=True, slots=True)
class DevicePitch:
    degrees: float
    sheets: tuple[Path, ...]
    muzzle_pixels: tuple
    forward_screen: tuple
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
    document = json.loads((root / "data/spell_devices.json").read_text())
    bodies = {}
    for identity, row in document["devices"].items():
        broken = row.get("destruction")
        destruction = None if broken is None else DeviceDestruction(
            broken["fps"], broken["frameCount"],
            MappingProxyType({bank["pitchDegrees"]: tuple(root / "assets" / path for path in bank["sheets"])
                              for bank in broken["pitchBanks"]}),
            broken["wreckItemId"], tuple(root / "assets" / path for path in broken["wreckSheets"]),
        )
        banks = tuple(DevicePitch(
            bank["pitchDegrees"], tuple(root / "assets" / path for path in bank["sheets"]),
            tuple(tuple(tuple(tuple(point) for point in frames) for frames in rows)
                  for rows in bank["muzzlePixels"]),
            tuple(tuple(tuple(point) for point in rows) for rows in bank["forwardScreen"]),
            tuple(bank["muzzleHeightStepsByRow"]),
        ) for bank in row["pitchBanks"])
        bodies[identity] = DeviceArt(identity, tuple(row["cell"]), tuple(row["anchor"]),
            tuple(row["rows"]), row["fps"], row["releaseFrame"], row["frameCount"], row["scale"],
            row["operatorRecipe"], row["launchPitchDegrees"], row["controlDistanceFraction"], banks, destruction)
    return MappingProxyType({item: bodies[body] for item, body in document["bindings"].items()})


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
