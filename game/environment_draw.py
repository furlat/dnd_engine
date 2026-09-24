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


@lru_cache(maxsize=4)
def _sheet(path: Path) -> pygame.Surface:
    return pygame.image.load(path).convert_alpha()


@lru_cache(maxsize=256)
def _frame(path: Path, rect: tuple[int, int, int, int], scale: float) -> pygame.Surface:
    _, _, width, height = rect
    image = _sheet(path).subsurface(rect)
    return pygame.transform.scale(image, (max(1, round(width * scale)), max(1, round(height * scale))))


def environment_command(bank: EnvironmentBank, frame: int, *, identity: UUID,
                        position: tuple[int, int], elevation: float, pose: str,
                        boundary_pose: str | None, camera: Camera,
                        multiplier: tuple[float, float, float], flash: int | None = None,
                        role: str = "environment", frame_only: bool = False) -> DrawCommand:
    scale = bank.scale * camera.zoom
    region = (bank.frame_regions_by_pose.get(pose) if frame_only else
              bank.frames_by_pose[pose][frame] if bank.frames_by_pose else None)
    if region is not None:
        path, rect = region.path, region.rect
    else:
        path = bank.frame_path if frame_only else bank.path
        assert path is not None
        width, height = bank.cell
        rect = frame * width, bank.rows.index(pose) * height, width, height
    image = device_treatment(_frame(path, rect, scale),
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
    if bank.actor_depth is None:
        return None
    region = bank.depth_frames_by_pose[pose][frame] if bank.depth_frames_by_pose else None
    path = region.path if region is not None else bank.depth_path
    if path is None:
        return None
    # The source ground origin is mounted within the tile independently of the
    # physical edge's painter contact. Decode depth relative to that same origin.
    ground_key = painter_key(position, elevation_steps=0,
        quadrant=camera.quadrant, role="object", identity="depth_origin")[1]
    origin_offset = (ground_key + (bank.ground_origins_by_pose[pose][1] - bank.pivots_by_pose[pose][1]) * bank.scale
                     - command.key[1])
    return FixtureDepthSample(index, path, bank.actor_depth, pose, frame,
        command.surface.get_size(), (0, 0, *command.surface.get_size()), bank.scale,
        origin_offset, source_rect=region.rect if region is not None else None)
