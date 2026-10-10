"""Pygame drawing for the pure mechanism projectile sampler."""

from functools import lru_cache
from math import cos, degrees, sin
import pygame
from game.asset_types import AssetSpec
from game.draw_commands import DrawCommand
from game.projection import Camera, painter_key
from game.mechanism_projectile import MechanismProjectileCue, MechanismProjectileSample


@lru_cache(maxsize=128)
def _rotated(image: pygame.Surface, rotation: float) -> pygame.Surface:
    return pygame.transform.rotate(image, -degrees(rotation)) if rotation else image


def mechanism_projectile_draw_command(cue: MechanismProjectileCue, sample: MechanismProjectileSample,
                                      image: pygame.Surface, spec: AssetSpec, camera: Camera) -> DrawCommand:
    """Use the existing cached surface and preserve its authored center when rotating."""
    factor = spec.scale * camera.zoom
    dx = image.width / 2 - spec.pivot[0] * factor
    dy = image.height / 2 - spec.pivot[1] * factor
    x = sample.anchor[0] + dx * cos(sample.rotation) - dy * sin(sample.rotation)
    y = sample.anchor[1] + dx * sin(sample.rotation) + dy * cos(sample.rotation)
    image = _rotated(image, sample.rotation)
    return DrawCommand(painter_key(sample.grid, elevation_steps=sample.elevation_steps,
        quadrant=camera.quadrant, role="projectile", identity=str(cue.event_uuid)),
        image, (round(x - image.width / 2), round(y - image.height / 2)), 0,
        (cue.event_uuid, sample.grid, sample.asset_id, "current", None, "authored",
         "mechanism_projectile", sample.elevation_steps,
         str(cue.mechanism_uuid) if cue.mechanism_uuid is not None else None, sample.progress))
