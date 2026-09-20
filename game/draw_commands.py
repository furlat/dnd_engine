"""Passive draw values shared by animation sampling and the map compositor."""

from typing import NamedTuple

import pygame

from game.area_media import AreaLayer


class DrawCommand(NamedTuple):
    key: tuple[int, float, float, int, tuple[str, ...]]
    surface: pygame.Surface
    destination: tuple[int, int]
    blend: int
    evidence: tuple[object, ...]
    # Keep raw pixels until the compositor has the actual receiving silhouettes.
    area: AreaLayer | None = None
