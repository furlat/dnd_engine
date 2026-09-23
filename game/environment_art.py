"""Authored environment atlases; native state selects the finite bank."""

from bisect import bisect_right
from dataclasses import dataclass
from functools import lru_cache
import json
from pathlib import Path
from types import MappingProxyType
from typing import Literal, Mapping

from game.animation_types import PropDepth


@dataclass(frozen=True, slots=True)
class EnvironmentBank:
    identity: str
    path: Path
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


def environment_art_from_document(document: dict, asset_root: Path) -> EnvironmentArt:
    """Decode explicit resources once; no raster reads or source verification."""
    banks = {}
    for identity, row in document["banks"].items():
        frame_count = row["frame_count"]
        times = (tuple(row["sample_times_ms"]) if "sample_times_ms" in row
                 else tuple(index * 1000 / row["fps"] for index in range(frame_count)))
        depth = row.get("actor_depth")
        registration = None if depth is None else PropDepth(
            identity + ".depth", tuple(depth["cell"]),
            MappingProxyType({pose: index for index, pose in enumerate(row["rows"])}),
            tuple(depth["depth_range"]), MappingProxyType(depth["pixels_per_unit_by_pose"]),
        )
        banks[identity] = EnvironmentBank(
            identity, asset_root / row["path"], tuple(row["cell"]),
            tuple(row["ground_pivot"]),
            MappingProxyType({pose: tuple(point) for pose, point in row["pivots_by_pose"].items()}),
            tuple(row["rows"]), row["scale"], frame_count, times, row["duration_ms"],
            MappingProxyType({pose: tuple(row.get("ground_origins_by_pose", {}).get(
                pose, row["ground_pivot"])) for pose in row["rows"]}),
            asset_root / row["frame_path"] if "frame_path" in row else None,
            asset_root / row["leaf_path"] if "leaf_path" in row else None,
            asset_root / depth["path"] if depth is not None else None, registration,
            row.get("release_frame"),
            row.get("state_change_frame", 0),
        )
    doors = {identity: EnvironmentDoorArt(
        MappingProxyType({mode: banks[key] for mode, key in row["openings"].items()}),
        MappingProxyType({mode: banks[key] for mode, key in row["destructions"].items()}),
        row["pose_offset"],
        MappingProxyType(row["frame_resource_by_pose"]),
    ) for identity, row in document["doors"].items()}
    traps = {identity: EnvironmentTrapArt(
        banks[row["intact"]], MappingProxyType(row["state_frames"]),
        MappingProxyType({mode: banks[key] for mode, key in row["destructions"].items()}),
    ) for identity, row in document["traps"].items()}
    wrecks = {identity: EnvironmentWreckArt(row["source_item_id"], row.get("outcome"))
              for identity, row in document["wrecks"].items()}
    props = {identity: EnvironmentPropArt(row.get("state_field"),
        MappingProxyType({state: banks[key] for state, key in row["intact"].items()}),
        MappingProxyType({state: banks[key] for state, key in row["destructions"].items()}),
    ) for identity, row in document.get("props", {}).items()}
    return EnvironmentArt(MappingProxyType(banks), MappingProxyType(doors),
                          MappingProxyType(traps), MappingProxyType(wrecks), MappingProxyType(props))


@lru_cache(maxsize=1)
def load_environment_art() -> EnvironmentArt:
    root = Path(__file__).resolve().parent
    document = json.loads((root / "data/environment_art.json").read_text())
    return environment_art_from_document(document, root / "assets")
