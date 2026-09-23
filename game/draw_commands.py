"""Passive draw values shared by animation sampling and the map compositor."""

from typing import NamedTuple

import numpy as np
import pygame

from game.area_media import AreaLayer
from game.volume_media import SurfaceVolume


class DrawCommand(NamedTuple):
    key: tuple[int, float, float, int, tuple[str, ...]]
    surface: pygame.Surface
    destination: tuple[int, int]
    blend: int
    evidence: tuple[object, ...]
    # Keep raw pixels until the compositor has the actual receiving silhouettes.
    area: AreaLayer | None = None
    # Optional per-pixel ground depth, aligned as (width, height) in painter units.
    world_depth: np.ndarray | None = None
    volume: SurfaceVolume | None = None
    # Components of one authored composite share world cuts and retain layer order.
    world_depth_group: tuple[str, ...] | None = None
