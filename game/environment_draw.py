"""Raster adapter for authored environment poses and persistent remains."""

from functools import lru_cache
from pathlib import Path
from typing import Mapping
from uuid import UUID

import pygame
import numpy as np

from game.device_draw import device_treatment
from game.draw_commands import DrawCommand
from game.environment_art import EnvironmentBank, load_environment_art
from game.environment_art import prop_state_key
from game.player_facts import PlayerObject
from dnd.core.item_types import ItemIntegrity
from game.fixture_depth import FixtureDepthSample
from game.projection import Camera, HEIGHT_STEP_PIXELS, camera_pose, painter_key, project_screen


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
                        role: str = "environment", frame_only: bool = False,
                        flat_ground: bool = False) -> DrawCommand:
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
    destination = (round(origin[0] - pivot[0] * scale), round(origin[1] - pivot[1] * scale))
    depth = (np.broadcast_to(((destination[1] + np.arange(image.height) + .5 - camera.pan[1])
            / camera.zoom + elevation * HEIGHT_STEP_PIXELS)[None, :], image.get_size())
            if flat_ground else None)
    return DrawCommand(
        painter_key(position, elevation_steps=elevation, quadrant=camera.quadrant,
            role="object", identity=identity, boundary_poses=(boundary_pose,) if boundary_pose else ()),
        image, destination, 0,
        (identity, position, bank.identity, "current", None, "authored", role, elevation, pose, frame),
        world_depth=depth, role="environment_floor" if flat_ground else "other",
        support_height_steps=elevation)


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


def environment_selection_command(obj: PlayerObject, camera: Camera) -> DrawCommand | None:
    """Use a registered target region at the received object's exact mount."""
    art = load_environment_art().props.get(obj.item.item_id)
    if art is None or obj.item.integrity is ItemIntegrity.DESTROYED:
        return None
    direction = obj.placement.boundary_direction or obj.placement.orientation
    pose = camera_pose(direction.value if direction is not None else "east", camera.quadrant)
    region = art.selection_masks_by_pose.get(pose)
    state = prop_state_key(art, obj.item.is_open)
    bank = art.intact.get(state) if state is not None else None
    if region is None or bank is None:
        return None
    image = _frame(region.path, region.rect, bank.scale*camera.zoom)
    origin = project_screen(obj.placement.position, camera, elevation_steps=obj.placement.base_height_steps)
    pivot = bank.pivots_by_pose[pose]
    key = painter_key(obj.placement.position, elevation_steps=obj.placement.base_height_steps,
        quadrant=camera.quadrant, role="object", identity=obj.item.item_uuid,
        boundary_poses=(pose,) if obj.placement.boundary_direction is not None else ())
    if obj.item.supported_by_uuid is not None:
        key = (*key[:4], (str(obj.item.supported_by_uuid), "attached", str(obj.item.item_uuid)))
    return DrawCommand(key, image, (round(origin[0]-pivot[0]*bank.scale*camera.zoom),
        round(origin[1]-pivot[1]*bank.scale*camera.zoom)), 0, ())


def environment_aperture_image(item_id: str, pose: str, camera: Camera) -> pygame.Surface | None:
    """Explicit opening coverage, independent of target selection and sprite alpha."""
    prop = load_environment_art().props.get(item_id)
    region = prop.aperture_masks_by_pose.get(pose) if prop is not None else None
    bank = prop.intact.get('default') if prop is not None else None
    return _frame(region.path,region.rect,bank.scale*camera.zoom) if region is not None and bank is not None else None


def pick_environment_target(point: tuple[int, int], objects: Mapping[UUID, PlayerObject],
                            camera: Camera) -> UUID | None:
    commands = [(obj.item.item_uuid, command) for obj in objects.values()
                if (command := environment_selection_command(obj, camera)) is not None]
    for identity, command in sorted(commands, key=lambda row: row[1].key, reverse=True):
        x, y = point[0]-command.destination[0], point[1]-command.destination[1]
        if (0 <= x < command.surface.get_width() and 0 <= y < command.surface.get_height()
                and command.surface.get_at((x,y)).a):
            return identity
    return None
