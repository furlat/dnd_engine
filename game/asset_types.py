"""Passive registered images shared by world and actor presentation."""

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


@dataclass(frozen=True, slots=True)
class AssetSpec:
    asset_id: str
    path: Path
    native_size: tuple[int, int]
    pivot: tuple[float, float]
    scale: float


def image_resources(rows: Mapping[str, dict], root: Path) -> dict[str, AssetSpec]:
    """Read registration values without opening or auditing image files."""
    return {identity: AssetSpec(identity, root / row["path"], tuple(row["native_size"]),
        (float(row["pivot"][0]), float(row["pivot"][1])), float(row["scale"]))
        for identity, row in rows.items()}
