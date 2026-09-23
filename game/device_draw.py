"""Raster adapter for the same device body in idle and cast playback."""

from functools import lru_cache
from pathlib import Path

import pygame
import numpy as np

from game.device_art import DeviceArt, DeviceEmission, DeviceFacing
from game.draw_commands import DrawCommand
from game.projection import Camera, painter_key, project_screen


@lru_cache(maxsize=32)
def _sheet(path):
    return pygame.image.load(path).convert_alpha()


@lru_cache(maxsize=256)
def _frame(path, width: int, height: int, row: int, frame: int, scale: float) -> pygame.Surface:
    image = _sheet(path).subsurface((frame * width, row * height, width, height))
    return pygame.transform.scale(image, (max(1, round(width * scale)), max(1, round(height * scale))))


@lru_cache(maxsize=128)
def device_treatment(image: pygame.Surface, multiplier: tuple[float, float, float],
                     flash: int | None = None) -> pygame.Surface:
    if multiplier == (1, 1, 1) and flash is None:
        return image
    result = image.copy()
    if flash is not None:
        result.fill((flash >> 16 & 255, flash >> 8 & 255, flash & 255, 255),
                    special_flags=pygame.BLEND_RGBA_MULT)
    if max(multiplier) > 1:
        # Very-bright native lighting exceeds BLEND_RGBA_MULT's byte factor.
        # Use the static world-image RGB treatment; alpha stays unchanged.
        pixels = pygame.surfarray.pixels3d(result)
        pixels[...] = np.clip(pixels.astype(np.float32)
            * np.asarray(multiplier, dtype=np.float32), 0, 255).astype(np.uint8)
        del pixels
    else:
        result.fill((*[round(255 * value) for value in multiplier], 255), special_flags=pygame.BLEND_RGBA_MULT)
    return result


def device_draw_command(emission: DeviceEmission, frame: int, camera: Camera,
                        multiplier: tuple[float, float, float] | None = None) -> DrawCommand:
    return _body_draw_command(emission.item_uuid, emission.grid, emission.elevation_steps,
        emission.facing, emission.art, emission.bank.sheets[camera.quadrant], frame, camera,
        "device", emission.bank.degrees, multiplier)


def device_wreck_draw_command(identity: str, position: tuple[float, float], elevation: float,
                              facing: DeviceFacing, art: DeviceArt, camera: Camera, *,
                              elapsed_ms: float | None = None, pitch_degrees: float | None = None,
                              multiplier: tuple[float, float, float] | None = None) -> DrawCommand:
    """The observed remnant owns one body: finite break frames, then its wreck."""
    destruction = art.destruction
    assert destruction is not None
    if elapsed_ms is not None and elapsed_ms < destruction.frame_count * 1000 / destruction.fps:
        assert pitch_degrees is not None
        sheet = destruction.pitch_banks[pitch_degrees][camera.quadrant]
        frame = min(destruction.frame_count - 1, max(0, int(elapsed_ms * destruction.fps / 1000)))
    else:
        sheet, frame = destruction.wreck_sheets[camera.quadrant], 0
    return _body_draw_command(identity, position, elevation, facing, art, sheet, frame, camera,
                              "device_wreck", pitch_degrees, multiplier)


def _body_draw_command(identity: str, position: tuple[float, float], elevation: float,
                        facing: DeviceFacing, art: DeviceArt, sheet: Path, frame: int, camera: Camera,
                        role: str, pitch: float | None,
                        multiplier: tuple[float, float, float] | None) -> DrawCommand:
    width, height = art.cell
    row = art.rows.index(facing)
    scale = art.scale * camera.zoom
    image = _frame(sheet, width, height, row, frame, scale)
    if multiplier is not None:
        image = device_treatment(image, multiplier)
    point = project_screen(position, camera, elevation_steps=elevation)
    return DrawCommand(
        painter_key(position, elevation_steps=elevation, quadrant=camera.quadrant, role="object", identity=identity),
        image, (round(point[0] - art.anchor[0] * scale), round(point[1] - art.anchor[1] * scale)), 0,
        (identity, position, art.identity, "current", None, "authored", role, elevation, facing, frame, pitch),
    )
