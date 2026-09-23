"""Authored cables whose lifetime comes entirely from displayed sustained links."""

from dataclasses import dataclass
from functools import lru_cache
from math import ceil, floor, hypot
from typing import Mapping
from uuid import UUID

import numpy as np
import pygame

from game.actor_facts import PresentationTarget
from game.animation_types import Facing8
from game.assets import AssetCatalog, SurfaceCache
from game.device_art import DeviceEmission, device_muzzle_offset
from game.draw_commands import DrawCommand
from game.player_facts import PlayerState
from game.projection import Camera, HEIGHT_STEP_PIXELS, TILE_HEIGHT, TILE_WIDTH, painter_key, project_screen


@dataclass(frozen=True, slots=True)
class TetherSection:
    image: pygame.Surface
    offset: tuple[int, int]
    progress: float


@lru_cache(maxsize=128)
def _registered_sections(
    source: pygame.Surface, endpoints: tuple[tuple[float, float], tuple[float, float]],
    delta: tuple[float, float], width_scale: float, count: int,
) -> tuple[TetherSection, ...]:
    """Fit along the authored axis; preserve transverse width and nearest pixels.

    Sections share the same affine registration. Their own world depth lets the
    ordinary painter cover the cable with intervening bodies and wall segments.
    """
    start, end = endpoints
    sx, sy = end[0] - start[0], end[1] - start[1]
    source_length, target_length = hypot(sx, sy), hypot(*delta)
    if target_length < 1:
        return ()
    su, sv = (sx / source_length, sy / source_length), (-sy / source_length, sx / source_length)
    tu, tv = (delta[0] / target_length, delta[1] / target_length), (-delta[1] / target_length, delta[0] / target_length)
    length_scale = target_length / source_length
    corners = []
    for x, y in ((0, 0), (source.width, 0), (source.width, source.height), (0, source.height)):
        dx, dy = x - start[0], y - start[1]
        along, across = (dx * su[0] + dy * su[1]) * length_scale, (dx * sv[0] + dy * sv[1]) * width_scale
        corners.append((tu[0] * along + tv[0] * across, tu[1] * along + tv[1] * across))
    left, top = floor(min(p[0] for p in corners)), floor(min(p[1] for p in corners))
    right, bottom = ceil(max(p[0] for p in corners)), ceil(max(p[1] for p in corners))
    x, y = np.indices((max(1, right - left), max(1, bottom - top)), dtype=np.float32)
    x, y = x + left + .5, y + top + .5
    along, across = x * tu[0] + y * tu[1], x * tv[0] + y * tv[1]
    source_x = np.floor(start[0] + su[0] * along / length_scale + sv[0] * across / width_scale).astype(int)
    source_y = np.floor(start[1] + su[1] * along / length_scale + sv[1] * across / width_scale).astype(int)
    valid = (source_x >= 0) & (source_x < source.width) & (source_y >= 0) & (source_y < source.height)
    source_x, source_y = np.clip(source_x, 0, source.width - 1), np.clip(source_y, 0, source.height - 1)
    rgb = pygame.surfarray.array3d(source)[source_x, source_y]
    alpha = pygame.surfarray.array_alpha(source)[source_x, source_y] * valid
    section = np.clip(np.floor(along * count / target_length).astype(int), 0, count - 1)
    result = []
    for index in range(count):
        mask = (section == index) & (alpha > 0)
        xs, ys = np.nonzero(mask)
        if not len(xs):
            continue
        x0, x1, y0, y1 = int(xs.min()), int(xs.max()) + 1, int(ys.min()), int(ys.max()) + 1
        image = pygame.Surface((x1 - x0, y1 - y0), pygame.SRCALPHA)
        pygame.surfarray.blit_array(image, rgb[x0:x1, y0:y1])
        opacity = pygame.surfarray.pixels_alpha(image)
        opacity[:] = alpha[x0:x1, y0:y1] * mask[x0:x1, y0:y1]
        del opacity
        result.append(TetherSection(image, (left + x0, top + y0), (index + .5) / count))
    return tuple(result)


def _muzzle_world(emitter: DeviceEmission, frame: int) -> tuple[tuple[float, float], float]:
    """Recover painter placement from the four measured projections."""
    offsets = tuple(device_muzzle_offset(emitter, quadrant, frame) for quadrant in range(4))
    height = -sum(point[1] for point in offsets) / 4
    x, y = offsets[0][0], offsets[0][1] + height
    return ((emitter.grid[0] + x / TILE_WIDTH + y / TILE_HEIGHT,
             emitter.grid[1] - x / TILE_WIDTH + y / TILE_HEIGHT),
            emitter.elevation_steps + height / HEIGHT_STEP_PIXELS)


def sustained_draw_commands(
    state: PlayerState | PresentationTarget, catalog: AssetCatalog, cache: SurfaceCache,
    camera: Camera, presentation_time: float,
    devices: Mapping[UUID, tuple[DeviceEmission, int]],
) -> tuple[DrawCommand, ...]:
    """Join only disclosed endpoints and matching current slots; never native state."""
    senses = state.senses
    if senses is None:
        return ()
    result = []
    for identity, effect in senses.spatial_effects.items():
        binding = catalog.spatial_tethers.get(effect.content_ref.content_id)
        anchor, owner, slot = effect.anchor_position, effect.sustainer_item_uuid, effect.concentration_slot_uuid
        if binding is None or anchor is None or owner is None or slot is None:
            continue
        if owner not in devices or owner not in senses.objects or anchor not in senses.visible:
            continue
        obj, tile = state.objects.get(owner), state.tiles.get(anchor)
        if obj is None or tile is None or not any(row.slot_uuid == slot for row in obj.item.concentration_slots):
            continue
        emitter, body_frame = devices[owner]
        support = project_screen(emitter.grid, camera, elevation_steps=emitter.elevation_steps)
        offset = device_muzzle_offset(emitter, camera.quadrant, body_frame)
        start = (support[0] + offset[0] * camera.zoom, support[1] + offset[1] * camera.zoom)
        end = project_screen(anchor, camera, elevation_steps=tile.elevation_steps)
        delta = end[0] - start[0], end[1] - start[1]
        vectors: dict[Facing8, tuple[float, float]] = {
            facing: (points[1][0] - points[0][0], points[1][1] - points[0][1])
            for facing, points in binding.endpoints_by_facing.items()}
        facing = max(vectors, key=lambda key: (
            vectors[key][0] * delta[0] + vectors[key][1] * delta[1]) / hypot(*vectors[key]))
        frames = binding.frames_by_facing[facing]
        asset = frames[int(presentation_time * binding.fps) % len(frames)]
        grid, height = _muzzle_world(emitter, body_frame)
        count = max(1, ceil(max(abs(anchor[0] - grid[0]), abs(anchor[1] - grid[1])) * 4))
        sections = _registered_sections(cache.canonical(asset), binding.endpoints_by_facing[facing],
            delta, catalog.resources[asset].scale * camera.zoom, count)
        for index, section in enumerate(sections):
            t = section.progress
            position = (grid[0] + (anchor[0] - grid[0]) * t, grid[1] + (anchor[1] - grid[1]) * t)
            cell = floor(position[0] + .5), floor(position[1] + .5)
            if cell not in senses.visible:
                continue
            elevation = height + (tile.elevation_steps - height) * t
            result.append(DrawCommand(painter_key(position, elevation_steps=elevation, quadrant=camera.quadrant,
                role="projectile", identity=(str(identity), str(slot), str(index))), section.image,
                (round(start[0] + section.offset[0]), round(start[1] + section.offset[1])), 0,
                (identity, position, asset, "current", None, "authored", "sustained_tether",
                 elevation, slot, owner, start, end)))
    return tuple(result)
