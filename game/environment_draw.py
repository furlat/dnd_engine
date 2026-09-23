"""Raster adapter for authored environment poses and persistent remains."""

from functools import lru_cache
from pathlib import Path
from uuid import UUID

import pygame

from game.device_draw import device_treatment
from game.draw_commands import DrawCommand
from game.environment_art import EnvironmentBank
from game.fixture_depth import FixtureDepthSample
from game.projection import Camera, painter_key, project_screen


@lru_cache(maxsize=2)
def _sheet(path: Path) -> pygame.Surface:
    return pygame.image.load(path).convert_alpha()


@lru_cache(maxsize=256)
def _frame(path: Path, cell: tuple[int, int], row: int, frame: int,
           scale: float) -> pygame.Surface:
    width, height = cell
    image = _sheet(path).subsurface((frame * width, row * height, width, height))
    return pygame.transform.scale(image, (max(1, round(width * scale)), max(1, round(height * scale))))


def environment_command(bank: EnvironmentBank, frame: int, *, identity: UUID,
                        position: tuple[int, int], elevation: float, pose: str,
                        boundary_pose: str | None, camera: Camera,
                        multiplier: tuple[float, float, float], flash: int | None = None,
                        role: str = "environment", frame_only: bool = False) -> DrawCommand:
    scale = bank.scale * camera.zoom
    path = bank.frame_path if frame_only else bank.path
    assert path is not None
    image = device_treatment(_frame(path, bank.cell, bank.rows.index(pose), frame, scale),
                             multiplier, flash)
    origin = project_screen(position, camera, elevation_steps=elevation)
    pivot = bank.pivots_by_pose[pose]
    return DrawCommand(
        painter_key(position, elevation_steps=elevation, quadrant=camera.quadrant,
            role="object", identity=identity, boundary_poses=(boundary_pose,) if boundary_pose else ()),
        image, (round(origin[0] - pivot[0] * scale), round(origin[1] - pivot[1] * scale)), 0,
        (identity, position, bank.identity, "current", None, "authored", role, elevation, pose, frame))


def environment_depth_sample(command: DrawCommand, index: int, bank: EnvironmentBank,
                             pose: str, frame: int, camera: Camera, *,
                             position: tuple[int, int]) -> FixtureDepthSample | None:
    if bank.actor_depth is None or bank.depth_path is None:
        return None
    # The source ground origin is mounted within the tile independently of the
    # physical edge's painter contact. Decode depth relative to that same origin.
    ground_key = painter_key(position, elevation_steps=0,
        quadrant=camera.quadrant, role="object", identity="depth_origin")[1]
    origin_offset = (ground_key + (bank.ground_origins_by_pose[pose][1] - bank.pivots_by_pose[pose][1]) * bank.scale
                     - command.key[1])
    return FixtureDepthSample(index, bank.depth_path, bank.actor_depth, pose, frame,
        command.surface.get_size(), (0, 0, *command.surface.get_size()), bank.scale,
        origin_offset)
