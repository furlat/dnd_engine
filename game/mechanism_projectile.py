"""A recorded mechanism's directional sprite on the ordinary world painter."""

from dataclasses import dataclass
from functools import lru_cache
from math import atan2, cos, degrees, floor, hypot, pi, sin
from typing import Annotated
from uuid import UUID

import pygame
from pydantic import Field

from game.animation import ActorContact, body_elevation_steps, body_rig, rest_pose_offset
from game.animation_types import AnimationData, MechanismProjectileArt
from game.asset_types import AssetSpec
from game.draw_commands import DrawCommand
from game.projection import Camera, HEIGHT_STEP_PIXELS, TILE_WIDTH, inverse_plane, painter_key, project_screen


@dataclass(frozen=True, slots=True)
class MechanismProjectileTarget:
    grid: tuple[float, float]
    elevation_steps: float
    offsets_by_quadrant: tuple[tuple[float, float], ...]


@dataclass(frozen=True, slots=True)
class MechanismProjectileCue:
    event_uuid: UUID
    mechanism_uuid: UUID | None
    origin: tuple[float, float]
    origin_elevation_steps: float
    end: tuple[float, float]
    end_elevation_steps: float
    direction: tuple[int, int]
    art: Annotated[MechanismProjectileArt, Field(exclude=True)]
    release_ms: float
    arrival_ms: float
    target: MechanismProjectileTarget | None = None
    muzzle_visible: bool = True


@dataclass(frozen=True, slots=True)
class MechanismProjectileSample:
    asset_id: str
    anchor: tuple[float, float]
    rotation: float
    grid: tuple[float, float]
    elevation_steps: float
    progress: float


def mechanism_projectile_duration(origin: tuple[float, float], end: tuple[float, float],
                                  origin_elevation_steps: float, end_elevation_steps: float,
                                  art: MechanismProjectileArt) -> float:
    """One camera-independent flight clock over the disclosed native segment."""
    return hypot(end[0] - origin[0], end[1] - origin[1],
                 end_elevation_steps - origin_elevation_steps) * 1000 / art.speed_tiles_per_second


def mechanism_projectile_target(target: ActorContact, data: AnimationData) -> MechanismProjectileTarget:
    """Freeze the shared rig/body/rest registration while binding the historical cue."""
    rig = body_rig(data, target)
    socket = rig.body_anchor
    if socket is None:
        raise ValueError(f"actor rig has no authored body attachment: {target.rig_id}")
    factor = target.visual_scale * TILE_WIDTH / data.rig.TILE_W
    x = (socket.x - rig.cell_width / 2) * factor * target.visual_scale_x
    y = (socket.y - rig.cell_height + rig.origin_y_from_ground) * factor
    offsets = []
    for quadrant in range(4):
        rest_x, rest_y = rest_pose_offset(data, target, quadrant)
        offsets.append((x + rest_x * TILE_WIDTH / data.rig.TILE_W,
                        y + rest_y * TILE_WIDTH / data.rig.TILE_W))
    return MechanismProjectileTarget(target.grid, body_elevation_steps(target, data), tuple(offsets))


def sample_mechanism_projectile(cue: MechanismProjectileCue, elapsed_ms: float,
                                camera: Camera) -> MechanismProjectileSample | None:
    """Sample a fixed release socket and the retained endpoint without native lookups."""
    if not cue.release_ms <= elapsed_ms < cue.arrival_ms:
        return None
    progress = (elapsed_ms - cue.release_ms) / (cue.arrival_ms - cue.release_ms)
    angle = atan2(cue.direction[1], cue.direction[0])
    column = floor(angle / (pi / 4) + .5) % 8
    poses = ("e", "s", "w", "n")
    camera_pose = poses[camera.quadrant]
    fixture_pose = poses[(camera.quadrant + column // 2) % 4]
    muzzle = cue.art.muzzle_offsets_by_pose[fixture_pose]
    origin = project_screen(cue.origin, camera, elevation_steps=cue.origin_elevation_steps)
    start_height = cue.origin_elevation_steps + cue.art.muzzle_height_steps
    first = ((origin[0] + muzzle[0] * camera.zoom, origin[1] + muzzle[1] * camera.zoom)
             if cue.muzzle_visible else project_screen(cue.origin, camera, elevation_steps=start_height))
    end_height = cue.end_elevation_steps + cue.art.muzzle_height_steps
    last = project_screen(cue.end, camera, elevation_steps=end_height)
    if cue.target is not None:
        target = cue.target
        dx, dy = target.offsets_by_quadrant[camera.quadrant]
        point = project_screen(target.grid, camera, elevation_steps=target.elevation_steps)
        last = point[0] + dx * camera.zoom, point[1] + dy * camera.zoom
        end_height = target.elevation_steps - dy / HEIGHT_STEP_PIXELS
    vx, vy = cue.art.tip_offsets_by_pose[camera_pose][column]
    travel_x, travel_y = last[0] - first[0], last[1] - first[1]
    rotation = atan2(travel_y, travel_x) - atan2(vy, vx) if travel_x or travel_y else 0.0
    anchor = first[0] + travel_x * progress, first[1] + travel_y * progress
    height = start_height + (end_height - start_height) * progress
    return MechanismProjectileSample(cue.art.frames_by_pose[camera_pose][column], anchor, rotation,
        inverse_plane(anchor, camera, elevation_steps=height), height, progress)


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
