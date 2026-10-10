"""Frame-local raster coverage; only WorldHit crosses the UI command boundary."""

from dataclasses import dataclass
from typing import Literal

import numpy as np


InteractionKind = Literal["actor", "object", "aperture", "ground"]


@dataclass(frozen=True, slots=True)
class WorldHit:
    kind: InteractionKind
    identity: str
    position: tuple[float, float]
    support_height_steps: float


@dataclass(frozen=True, slots=True)
class SelectionCoverage:
    hit: WorldHit
    # Aligned with the owning DrawCommand surface, (width, height).
    mask: np.ndarray


@dataclass(frozen=True, slots=True)
class InteractionRegion:
    hit: WorldHit
    destination: tuple[int, int]
    mask: np.ndarray
    painter_order: int
