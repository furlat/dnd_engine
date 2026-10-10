"""Cached world-coordinate residue textures on disclosed floors and wall faces."""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass, field
from math import cos, floor, sin, sqrt
from collections.abc import Sequence

import numpy as np
import pygame

from game.projection import Camera, TILE_HEIGHT, TILE_WIDTH
from dnd.types.residues import ResidueEllipse, TileResidueState
from game.animation_types import BloodResponse, LandingTemplate, ParticleMediaAsset, RegionParticleStyle
from game.residue_media import ResidueRevealSample, landed_fraction, landing_template, surface_start_time


@dataclass(frozen=True, slots=True)
class ResidueSurfaceStyle:
    floor_atlas: str
    wall_atlas: str
    floor_opacity: float
    wall_opacity: float


@dataclass(frozen=True, slots=True)
class LiquidSurfaceStyle:
    """Local pool artwork; the received membership owns its actual tile."""

    asset: ParticleMediaAsset
    ellipse: ResidueEllipse
    opacity: float


@dataclass(frozen=True, slots=True)
class WallFace:
    """Authored face UV plane in source-image pixels, from top left."""

    origin: tuple[float, float]
    across: tuple[float, float]
    down: tuple[float, float]
    reverse: bool = False


@dataclass(slots=True)
class ResidueSurfaceCache:
    limit_bytes: int = 32 * 1024 * 1024
    images: OrderedDict[tuple, pygame.Surface] = field(default_factory=OrderedDict)
    decoded_bytes: int = 0
    rebuilds: int = 0
    # Keep settled kernel fields when another contribution begins landing.
    fields: OrderedDict[tuple, np.ndarray] = field(default_factory=OrderedDict)
    field_bytes: int = 0
    field_limit_bytes: int = 8 * 1024 * 1024
    field_rebuilds: int = 0


def _read(cache: ResidueSurfaceCache, key: tuple) -> pygame.Surface | None:
    image = cache.images.get(key)
    if image is not None:
        cache.images.move_to_end(key)
    return image


def _keep(cache: ResidueSurfaceCache, key: tuple, image: pygame.Surface) -> pygame.Surface:
    size = image.get_pitch() * image.height
    while cache.images and cache.decoded_bytes + size > cache.limit_bytes:
        _, old = cache.images.popitem(last=False)
        cache.decoded_bytes -= old.get_pitch() * old.height
    if size <= cache.limit_bytes:
        cache.images[key] = image
        cache.decoded_bytes += size
    cache.rebuilds += 1
    return image


def _variation(x: int, y: int) -> int:
    # Stable visual variation in world coordinates; no native seed/state.
    return ((x + 37) * 73856093 ^ (y + 19) * 19349663) % 997


def _motif(atlas: pygame.Surface, col: int, row: int) -> pygame.Surface:
    left, top = round(col * atlas.width / 4), round(row * atlas.height / 4)
    right, bottom = round((col + 1) * atlas.width / 4), round((row + 1) * atlas.height / 4)
    return atlas.subsurface((left, top, right - left, bottom - top))


def ground_residue_image(cache: ResidueSurfaceCache, atlas: pygame.Surface,
                         style: ResidueSurfaceStyle, position: tuple[int, int],
                         occupied: frozenset[tuple[int, int]], camera: Camera,
                         multiplier: tuple[float, float, float]) -> pygame.Surface:
    """Sample one tile from a continuous overlapping field and occupancy mask.

    The surrounding eight cells only control exposed edges. Adjacent tiles sample
    the same world texture at their join, rather than restarting an atlas stamp.
    """
    x, y = position
    neighborhood = tuple((x + dx, y + dy) in occupied
                         for dx in (-1, 0, 1) for dy in (-1, 0, 1))
    source_key = ("floor", style, position, neighborhood)
    key = (*source_key, camera.quadrant, camera.zoom, multiplier)
    result = _read(cache, key)
    if result is not None:
        return result
    texture = _read(cache, source_key)
    size = 32
    if texture is None:
        texture = pygame.Surface((size, size), pygame.SRCALPHA)
        origin_x, origin_y = x * size - size // 2, y * size - size // 2
        for gx in range(floor((origin_x - 55) / 48), floor((origin_x + size + 55) / 48) + 1):
            for gy in range(floor((origin_y - 55) / 48), floor((origin_y + size + 55) / 48) + 1):
                variant = _variation(gx, gy)
                motif = pygame.transform.scale(_motif(atlas, variant % 4, 0), (70, 70))
                motif = pygame.transform.rotate(motif, (variant % 4) * 90)
                motif.set_alpha(191)
                center_x = gx * 48 + 12 + (variant / 997 - .5) * 14
                texture.blit(motif, (round(center_x - origin_x - 35), gy * 48 + 12 - origin_y - 35))
        u, v = np.indices((size, size))
        distance = np.full((size, size), 99.0)
        for dx, dy, edge in ((-1, 0, u), (1, 0, size - 1 - u),
                             (0, -1, v), (0, 1, size - 1 - v)):
            if (x + dx, y + dy) not in occupied:
                distance = np.minimum(distance, edge)
        for dx, dy in ((-1, -1), (-1, 1), (1, -1), (1, 1)):
            if (x + dx, y + dy) not in occupied:
                distance = np.minimum(distance, np.hypot(u if dx < 0 else size - 1 - u,
                                                         v if dy < 0 else size - 1 - v))
        px, py = (u + origin_x) // 3, (v + origin_y) // 3
        noise = (((px + 37) * 73856093 ^ (py + 19) * 19349663) % 997) / 997
        threshold = 2 + noise * 4
        opacity = np.where(distance < threshold, 0, np.where(distance < threshold + 3, 110 / 255, 1))
        alpha = pygame.surfarray.pixels_alpha(texture)
        alpha[:] = np.rint(alpha * opacity * style.floor_opacity).astype(np.uint8)
        del alpha
        _keep(cache, source_key, texture)
    width, height = round(TILE_WIDTH * camera.zoom), round(TILE_HEIGHT * camera.zoom)
    px, py = np.indices((width, height), dtype=np.float32)
    dx = (px + .5 - width / 2) / width + (py + .5 - height / 2) / height
    dy = (py + .5 - height / 2) / height - (px + .5 - width / 2) / width
    dx, dy = ((dx, dy), (dy, -dx), (-dx, -dy), (-dy, dx))[camera.quadrant]
    sx, sy = np.floor((dx + .5) * size).astype(int), np.floor((dy + .5) * size).astype(int)
    admitted = (sx >= 0) & (sx < size) & (sy >= 0) & (sy < size)
    sx, sy = np.clip(sx, 0, size - 1), np.clip(sy, 0, size - 1)
    result = pygame.Surface((width, height), pygame.SRCALPHA)
    rgb = pygame.surfarray.pixels3d(result)
    rgb[:] = np.rint(pygame.surfarray.array3d(texture)[sx, sy] * np.asarray(multiplier)).astype(np.uint8)
    del rgb
    alpha = pygame.surfarray.pixels_alpha(result)
    alpha[:] = pygame.surfarray.array_alpha(texture)[sx, sy] * admitted
    del alpha
    return _keep(cache, key, result)


def _wall_texture(cache: ResidueSurfaceCache, atlas: pygame.Surface,
                  style: ResidueSurfaceStyle, line: float, along: float) -> pygame.Surface:
    key = ("wall-field", style, line, along)
    texture = _read(cache, key)
    if texture is not None:
        return texture
    texture = pygame.Surface((80, 192), pygame.SRCALPHA)
    origin = along * 64 - 40
    for index in range(floor((origin - 80) / 51), floor((origin + 160) / 51) + 1):
        variant = _variation(index, round(line * 2))
        width, height = 70 + variant % 37, 80 + variant % 100
        image = pygame.transform.scale(_motif(atlas, variant % 4, 0), (width, height))
        image = pygame.transform.flip(image, bool(variant % 2), False)
        image.set_alpha(200)
        texture.blit(image, (round(index * 51 - origin - width / 2), 192 - height))
    return _keep(cache, key, texture)


def wall_residue_image(cache: ResidueSurfaceCache, atlas: pygame.Surface,
                       style: ResidueSurfaceStyle, base: pygame.Surface, *,
                       base_key: tuple, scale: float, crop_origin: tuple[int, int],
                       faces: tuple[tuple[WallFace, float, float], ...]) -> pygame.Surface:
    """Multiply soot into authored face UVs, preserving base alpha/material.

    Each face supplies its physical boundary-line and wall-local distance. Only
    explicitly disclosed, camera-facing marked faces should reach this boundary.
    """
    key = ("wall", style, base_key, scale, crop_origin, faces)
    result = _read(cache, key)
    if result is not None:
        return result
    result = base.copy()
    px, py = np.indices(base.get_size(), dtype=np.float32)
    rgb = pygame.surfarray.pixels3d(result)
    for face, line, along in faces:
        texture = _wall_texture(cache, atlas, style, line, along)
        ax, ay = face.across
        bx, by = face.down
        x = (px + crop_origin[0] + .5) / scale - face.origin[0]
        y = (py + crop_origin[1] + .5) / scale - face.origin[1]
        determinant = ax * by - ay * bx
        u, v = (x * by - y * bx) / determinant, (y * ax - x * ay) / determinant
        admitted = (u >= 0) & (u < 1) & (v >= 0) & (v < 1)
        u = 1 - u if face.reverse else u
        sx, sy = np.clip((u * 80).astype(int), 0, 79), np.clip((v * 192).astype(int), 0, 191)
        alpha = pygame.surfarray.array_alpha(texture)[sx, sy] / 255 * style.wall_opacity * admitted
        color = pygame.surfarray.array3d(texture)[sx, sy] / 255
        rgb[:] = np.rint(rgb * (1 - (1 - color) * alpha[:, :, None])).astype(np.uint8)
    del rgb
    return _keep(cache, key, result)


def geometric_residue_image(cache: ResidueSurfaceCache, asset: ParticleMediaAsset,
                             position: tuple[int, int], residue: TileResidueState, camera: Camera,
                             multiplier: tuple[float, float, float],
                             reveals: Sequence[ResidueRevealSample] = (), *,
                             pool: ResidueEllipse | None = None) -> pygame.Surface:
    """Sample retained local ellipses; no template is refitted at a tile seam."""
    style = asset.region
    assert style is not None
    active = tuple(row for row in reveals if row.reveal.position == position
                   and row.reveal.after.condition_uuid == residue.condition_uuid)
    fractions = tuple(tuple(tuple(landed_fraction(p, style.families[row.reveal.pattern],
                                                  row.reveal.response, row.elapsed_ms / 1000)
                              for p in template.particles)
                        for template in style.templates) for row in active)
    surface_ages = tuple(_surface_age(row) for row in active)
    unshaped = max(0, residue.amount - sum(row.amount for row in residue.contributions if row.ellipses))
    source_key = ("deposited", asset.assetId, position, residue.max_amount, residue.contributions,
                  (pool, unshaped) if pool is not None else None,
                  tuple((row.reveal.before, row.reveal.after,
                         row.reveal.response, age) for row, age in zip(active, surface_ages)), fractions)
    key = (*source_key, camera.quadrant, camera.zoom, multiplier)
    result = _read(cache, key)
    if result is not None:
        return result
    texture = _read(cache, source_key)
    size = 64
    if texture is None:
        texture = _deposit_texture(cache, asset, position, residue, active, fractions, surface_ages, size, pool)
        _keep(cache, source_key, texture)
    return _project_texture(cache, key, texture, camera, multiplier)


def liquid_surface_image(cache: ResidueSurfaceCache, style: LiquidSurfaceStyle,
                         position: tuple[int, int], camera: Camera,
                         multiplier: tuple[float, float, float], *,
                         amount: int = 1, max_amount: int = 1) -> pygame.Surface:
    """Draw a data-authored pool without manufacturing a native deposit."""
    region = style.asset.region
    assert region is not None and region.primitive == "liquid"
    source_key = ("liquid-pool", style.asset.assetId, style.ellipse, style.opacity,
                  position, amount, max_amount)
    key = (*source_key, camera.quadrant, camera.zoom, multiplier)
    result = _read(cache, key)
    if result is not None:
        return result
    texture = _read(cache, source_key)
    if texture is None:
        world = style.ellipse.model_copy(update={"center": (
            position[0] + style.ellipse.center[0], position[1] + style.ellipse.center[1])})
        template = landing_template(region, world)
        field = _deposit_patch(cache, style.asset.assetId, style.ellipse, template,
            (amount / max_amount,) * len(template.particles), region.primitive, 64)
        texture = pygame.Surface((64, 64), pygame.SRCALPHA)
        _shade_liquid(texture, region, position, field)
        alpha = pygame.surfarray.pixels_alpha(texture)
        alpha[:] = np.rint(alpha * style.opacity).astype(np.uint8)
        del alpha
        _keep(cache, source_key, texture)
    return _project_texture(cache, key, texture, camera, multiplier)


def _project_texture(cache: ResidueSurfaceCache, key: tuple, texture: pygame.Surface,
                     camera: Camera, multiplier: tuple[float, float, float]) -> pygame.Surface:
    """The same tile-plane projection for native deposits and local pool media."""
    size = texture.width
    width, height = round(TILE_WIDTH * camera.zoom), round(TILE_HEIGHT * camera.zoom)
    px, py = np.indices((width, height), dtype=np.float32)
    dx = (px + .5 - width / 2) / width + (py + .5 - height / 2) / height
    dy = (py + .5 - height / 2) / height - (px + .5 - width / 2) / width
    dx, dy = ((dx, dy), (dy, -dx), (-dx, -dy), (-dy, dx))[camera.quadrant]
    sx, sy = np.floor((dx + .5) * size).astype(int), np.floor((dy + .5) * size).astype(int)
    admitted = (sx >= 0) & (sx < size) & (sy >= 0) & (sy < size)
    sx, sy = np.clip(sx, 0, size - 1), np.clip(sy, 0, size - 1)
    result = pygame.Surface((width, height), pygame.SRCALPHA)
    rgb = pygame.surfarray.pixels3d(result)
    rgb[:] = np.rint(pygame.surfarray.array3d(texture)[sx, sy] * np.asarray(multiplier)).astype(np.uint8)
    del rgb
    alpha = pygame.surfarray.pixels_alpha(result)
    alpha[:] = pygame.surfarray.array_alpha(texture)[sx, sy] * admitted
    del alpha
    return _keep(cache, key, result)


def _field_noise(x: np.ndarray, y: np.ndarray, seed: int) -> np.ndarray:
    """The artist's compact value noise in common world coordinates."""
    ix, iy = np.floor(x).astype(np.int64), np.floor(y).astype(np.int64)
    u, v = x - ix, y - iy
    u, v = u * u * (3 - 2 * u), v * v * (3 - 2 * v)

    def random(a, b):
        n = ((a + b * 4099 + seed * 65537 + 101) * 1597334677) & 0xFFFFFFFF
        n ^= n >> 16
        return ((n * 2246822519) & 0xFFFFFFFF) / 4294967296

    return ((random(ix, iy) * (1 - u) + random(ix + 1, iy) * u) * (1 - v)
            + (random(ix, iy + 1) * (1 - u) + random(ix + 1, iy + 1) * u) * v)


def _deposit_texture(cache: ResidueSurfaceCache, asset: ParticleMediaAsset, position: tuple[int, int], residue: TileResidueState,
                     active: tuple[ResidueRevealSample, ...], fractions: tuple[tuple[tuple[float, ...], ...], ...],
                     surface_ages: tuple[float, ...], size: int, pool: ResidueEllipse | None) -> pygame.Surface:
    style = asset.region
    assert style is not None
    px, py = np.indices((size, size), dtype=np.float32)
    x, y = (px + .5) / size - .5, (py + .5) / size - .5
    field = np.zeros((size, size), dtype=np.float32)
    fragments = np.zeros((size, size), dtype=bool)
    fresh_fields: dict[int, np.ndarray] = {}
    unshaped = max(0, residue.amount - sum(row.amount for row in residue.contributions if row.ellipses))
    if pool is not None and unshaped:
        world = pool.model_copy(update={"center": (position[0] + pool.center[0], position[1] + pool.center[1])})
        template = landing_template(style, world)
        field += _deposit_patch(cache, asset.assetId, pool, template,
            (unshaped / residue.max_amount,) * len(template.particles), style.primitive, size)
    for contribution in residue.contributions:
        reductions = []
        for index, (row, template_fractions) in enumerate(zip(active, fractions)):
            changed = next((c for c in row.reveal.after.contributions if c.ellipses == contribution.ellipses), None)
            if changed is None or contribution.amount < changed.amount:
                continue
            before = next((c.amount for c in row.reveal.before.contributions if c.ellipses == contribution.ellipses), 0) if row.reveal.before else 0
            if changed.amount > before:
                reductions.append((index, changed.amount - before, template_fractions))
        for ellipse in contribution.ellipses:
            world = ellipse.model_copy(update={"center": (ellipse.center[0] + position[0], ellipse.center[1] + position[1])})
            template = landing_template(style, world)
            template_index = style.templates.index(template)
            units = tuple(max(0, contribution.amount - sum(delta * (1 - landed[template_index][p_index])
                           for _, delta, landed in reductions)) for p_index in range(len(template.particles)))
            patch = _deposit_patch(cache, asset.assetId, ellipse, template,
                                   tuple(value / residue.max_amount for value in units), style.primitive, size)
            if style.primitive == "fragments":
                fragments |= patch
            else:
                field += patch
                for index, delta, landed in reductions:
                    response = active[index].reveal.response
                    age = surface_ages[index]
                    if response is None or response.surfaceSeconds <= age:
                        continue
                    # Shade only this fresh field increment. An earlier deposit,
                    # even in the same retained ellipse, remains ordinary blood.
                    previous = _deposit_patch(cache, asset.assetId, ellipse, template,
                        tuple(max(0, value - delta * amount) / residue.max_amount
                              for value, amount in zip(units, landed[template_index])), style.primitive, size)
                    fresh_fields.setdefault(index, np.zeros_like(field))[:] += np.maximum(0, patch - previous)
    texture = pygame.Surface((size, size), pygame.SRCALPHA)
    rgb, alpha = pygame.surfarray.pixels3d(texture), pygame.surfarray.pixels_alpha(texture)
    if style.primitive == "fragments":
        assert style.palette is not None
        edge = fragments & ~(np.roll(fragments, 1, axis=0) & np.roll(fragments, 1, axis=1))
        colors = np.array([((c >> 16) & 255, (c >> 8) & 255, c & 255) for c in style.palette])
        rgb[:] = np.where(edge[:, :, None], colors[2], colors[1])
        alpha[:] = fragments * 240
    else:
        shares = {index: np.divide(fresh, field, out=np.zeros_like(field), where=field > 0)
                  for index, fresh in fresh_fields.items()}
        del rgb, alpha
        _shade_liquid(texture, style, position, field)
        rgb, alpha = pygame.surfarray.pixels3d(texture), pygame.surfarray.pixels_alpha(texture)
        wx, wy = (x + position[0]) * size, (y + position[1]) * size
        for index, share in shares.items():
            row = active[index]
            assert row.reveal.response is not None
            _shade_fresh_blood(rgb, alpha, wx, wy, share, row.reveal.response, surface_ages[index])
    del rgb, alpha
    return texture


def _shade_liquid(texture: pygame.Surface, style: RegionParticleStyle,
                  position: tuple[int, int], field: np.ndarray) -> None:
    """Shared authored liquid shading for injury shapes and settled pools."""
    size = texture.width
    px, py = np.indices((size, size), dtype=np.float32)
    x, y = (px + .5) / size - .5, (py + .5) / size - .5
    # Noise is stable in world coordinates across tiles and camera rotations.
    wx, wy = (x + position[0]) * size, (y + position[1]) * size
    n, fine = _field_noise(wx / 9, wy / 9, 0), _field_noise(wx / 2.8, wy / 2.8, 3)
    field = field.copy()
    field *= .72 + n * .65
    threshold = .13 + (fine - .5) * .045
    depth = np.clip((field - threshold) * 1.6, 0, 1)
    rim = np.maximum(0, 1 - depth * 5)
    wet = _field_noise(wx / 17, wy / 13, 9)
    highlight = (depth > .12) & (depth < .5) & (wet > .66) & (_field_noise(wx / 4, wy / 4, 8) > .56)
    red = 88 - 38 * depth + rim * 24 + (n - .5) * 27 + highlight * 37
    rgb, alpha = pygame.surfarray.pixels3d(texture), pygame.surfarray.pixels_alpha(texture)
    if style.palette is None:
        rgb[:] = np.stack((red, 8 - 3 * depth + highlight * 10, 15 - 5 * depth + highlight * 9), axis=2).round().astype(np.uint8)
    else:
        colors = np.array([((c >> 16) & 255, (c >> 8) & 255, c & 255) for c in style.palette])
        t = np.clip((red - 35) / 105, 0, 1)
        low, high = np.where((t < .55)[:, :, None], colors[0], colors[1]), np.where((t < .55)[:, :, None], colors[1], colors[2])
        mix = np.where(t < .55, t / .55, (t - .55) / .45)[:, :, None]
        rgb[:] = np.rint(low * (1 - mix) + high * mix).astype(np.uint8)
    alpha[:] = np.where(field >= threshold, np.minimum(246, 120 + depth * 150), 0).round().astype(np.uint8)
    del rgb, alpha


def _surface_age(row: ResidueRevealSample) -> float:
    response = row.reveal.response
    if response is None or response.surfaceSeconds == 0:
        return 0
    first = surface_start_time(row.reveal.asset.assetId, row.reveal.pattern, response)
    age = max(0, row.elapsed_ms / 1000 - first)
    return response.surfaceSeconds if age >= response.surfaceSeconds else floor(age * 12) / 12


def _shade_fresh_blood(rgb: np.ndarray, alpha: np.ndarray, wx: np.ndarray, wy: np.ndarray,
                       share: np.ndarray, response: BloodResponse, age: float) -> None:
    """The handoff's finite internal treatment, confined to new landed blood."""
    t = floor(max(0, age) * 12) / 12
    strength = np.clip(share, 0, 1) * max(0, 1 - t / response.surfaceSeconds) * (alpha > 0)
    n, vein, fine = (_field_noise(wx / 4, wy / 4, 31), _field_noise(wx / 12, wy / 12, 47),
                     _field_noise(wx / 2, wy / 2, 11))
    rim = alpha < 175
    color = np.zeros((*alpha.shape, 3), dtype=np.float32)
    mix = np.zeros(alpha.shape, dtype=np.float32)

    def paint(mask: np.ndarray, tint: tuple[int, int, int], amount: float) -> None:
        color[mask] = tint
        mix[mask] = amount

    if response.detail == "acid":
        paint((rim & (n > .42)) | (~rim & (n > .61)), (122, 131, 48), .8)
    elif response.detail == "necrotic":
        paint(alpha > 0, (24, 11, 18), .4)
        paint((n > .55) & (fine > .45), (80, 112, 49), .7)
    elif response.detail == "poison":
        ribbon = np.abs(vein - .5)
        paint((ribbon < .085) & (n > .35), (113, 128, 39), .82)
        paint((ribbon >= .085) & (ribbon < .11) & (fine > .5), (179, 163, 93), .72)
    elif response.detail == "fire":
        paint(alpha > 0, (34, 12, 14), .3)
        paint((n > .62) & (fine > .55), (183, 85, 32), .7)
    elif response.detail == "radiant":
        paint((np.abs(vein - .52) < .085) & (fine > .46), (207, 170, 83), .88)
    elif response.detail == "lightning" and floor(t * 12) % 3 != 0:
        paint((np.abs(vein - .5) < .04) & (n > .37), (150, 184, 220), .88)
    elif response.detail == "psychic":
        paint(np.abs(vein - .5) < .025, (108, 46, 102), .45)
    elif response.detail == "thunder":
        paint(np.abs(n - .5) < .03, (121, 31, 41), .4)
    weight = (mix * strength)[:, :, None]
    rgb[:] = np.rint(rgb * (1 - weight) + color * weight).astype(np.uint8)


def _deposit_patch(cache: ResidueSurfaceCache, asset_id: str, ellipse: ResidueEllipse,
                   template: LandingTemplate, fractions: tuple[float, ...], primitive: str,
                   size: int) -> np.ndarray:
    key = (asset_id, ellipse, template.seed, fractions, size)
    cached = cache.fields.get(key)
    if cached is not None:
        cache.fields.move_to_end(key)
        return cached
    px, py = np.indices((size, size), dtype=np.float32)
    dx, dy = (px + .5) / size - .5 - ellipse.center[0], (py + .5) / size - .5 - ellipse.center[1]
    co, si = cos(ellipse.angle), sin(ellipse.angle)
    u, v = (dx * co + dy * si) / ellipse.radius_x, (-dx * si + dy * co) / ellipse.radius_y
    patch = np.zeros((size, size), dtype=bool if primitive == "fragments" else np.float32)
    for particle, fraction in zip(template.particles, fractions):
        if fraction == 0:
            continue
        scale = sqrt(fraction)
        tx, ty = particle.target
        if primitive == "fragments":
            vertices = tuple((tx + (a - tx) * scale, ty + (b - ty) * scale) for a, b in particle.fragment)
            inside = np.zeros((size, size), dtype=bool)
            for (ax, ay), (bx, by) in zip(vertices, (*vertices[1:], vertices[0])):
                if by != ay:
                    inside ^= ((ay > v) != (by > v)) & (u < (bx - ax) * (v - ay) / (by - ay) + ax)
            patch |= inside
        else:
            for kernel in particle.kernels:
                a, b = tx + (kernel.x - tx) * scale, ty + (kernel.y - ty) * scale
                kc, ks = cos(kernel.angle), sin(kernel.angle)
                du, dv = u - a, v - b
                q = ((du * kc + dv * ks) / (kernel.rx * scale)) ** 2 + ((-du * ks + dv * kc) / (kernel.ry * scale)) ** 2
                patch += kernel.mass * np.maximum(0, 1 - q / 1.5) ** 2
    while cache.fields and cache.field_bytes + patch.nbytes > cache.field_limit_bytes:
        _, removed = cache.fields.popitem(last=False)
        cache.field_bytes -= removed.nbytes
    if patch.nbytes <= cache.field_limit_bytes:
        cache.fields[key] = patch
        cache.field_bytes += patch.nbytes
    cache.field_rebuilds += 1
    return patch
