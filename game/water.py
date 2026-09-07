"""Vectorized software reproduction of the imported Unity Water material."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence, cast

import numpy as np
import pygame

from game.projection import project_world


@dataclass(frozen=True, slots=True)
class WaterSupportInput:
    """One painter-slot support packed into an owner-chunk calculation."""

    source_origin_px: tuple[float, float]
    destination_px: tuple[int, int]
    multiplier: tuple[float, float, float]


@dataclass(frozen=True, slots=True)
class WaterBatchOutput:
    """Scattered per-support Surfaces from one vector material invocation."""

    surfaces: tuple[pygame.Surface, ...]
    destinations: tuple[tuple[int, int], ...]
    evaluated_pixels: int
    destination_bounds: tuple[int, int, int, int]


def water_source_origin(
    position: tuple[int, int],
    *,
    pivot: tuple[float, float],
    asset_scale: float,
) -> tuple[float, float]:
    """Return canonical world sampling origin, independent of view and height."""
    contact_x, contact_y = project_world(position, elevation_steps=0, quadrant=0)
    return (
        contact_x - pivot[0] * asset_scale,
        contact_y - pivot[1] * asset_scale,
    )


def _number(material: Mapping[str, object], key: str) -> float:
    value = material.get(key)
    if type(value) not in (int, float):
        raise ValueError(f"Water material {key} must be numeric")
    return float(cast(float | int, value))


def _vector(
    material: Mapping[str, object],
    key: str,
    size: int,
) -> np.ndarray:
    value = material.get(key)
    if (
        type(value) is not list
        or len(value) != size
        or any(type(part) not in (int, float) for part in value)
    ):
        raise ValueError(f"Water material {key} must contain {size} numbers")
    return np.asarray(value, dtype=np.float32)


def _sample_repeat_nearest(
    texture: np.ndarray,
    uv_x: np.ndarray,
    uv_y: np.ndarray,
    channels: int,
) -> np.ndarray:
    """Sample an x-major RGB texture with repeat/nearest semantics."""
    if (
        texture.ndim != 3
        or uv_x.shape != uv_y.shape
        or uv_x.ndim != 1
        or channels <= 0
        or texture.shape[2] < channels
    ):
        raise ValueError("Water sampler requires an x-major color texture")
    width, height = texture.shape[:2]
    x = np.floor(uv_x * width).astype(np.int32)
    y = np.floor(uv_y * height).astype(np.int32)
    if width & (width - 1) == 0:
        x &= width - 1
    else:
        x %= width
    if height & (height - 1) == 0:
        y &= height - 1
    else:
        y %= height
    flat_indices = x * height + y
    sampled = np.take(
        texture.reshape((-1, texture.shape[2])),
        flat_indices,
        axis=0,
    )[:, :channels]
    values = sampled.astype(np.float32, copy=False)
    if np.issubdtype(sampled.dtype, np.integer):
        values = values * np.float32(1.0 / 255.0)
    return values


def shade_water_packed(
    *,
    mask_alpha: np.ndarray,
    input_pixels: np.ndarray,
    source_origins_px: np.ndarray,
    global_framebuffer_pixels: np.ndarray,
    framebuffer_size: tuple[int, int],
    tile_width_px: float,
    render_scale: float,
    time_seconds: float,
    ripple_texture: np.ndarray,
    normal_texture: np.ndarray,
    material: Mapping[str, object],
) -> np.ndarray:
    """Evaluate exact straight-output shader RGBA for one packed chunk call."""
    count = mask_alpha.shape[0]
    if (
        mask_alpha.shape != (count,)
        or input_pixels.shape != (count, 2)
        or source_origins_px.shape != (count, 2)
        or global_framebuffer_pixels.shape != (count, 2)
    ):
        raise ValueError("Water packed inputs must share one N-row shape")
    if tile_width_px <= 0 or render_scale <= 0:
        raise ValueError("Water tile width and render scale must be positive")
    if framebuffer_size[0] <= 0 or framebuffer_size[1] <= 0:
        raise ValueError("Water framebuffer dimensions must be positive")

    mask = mask_alpha.astype(np.float32, copy=False)
    input_xy = input_pixels.astype(np.float32, copy=False)
    origins = source_origins_px.astype(np.float32, copy=False)
    globals_xy = global_framebuffer_pixels.astype(np.float32, copy=False)
    world_x = origins[:, 0] + input_xy[:, 0] / render_scale
    world_y = -origins[:, 1] - input_xy[:, 1] / render_scale
    inverse_tile_width = np.float32(1.0 / tile_width_px)
    world_x *= inverse_tile_width
    world_y *= inverse_tile_width
    uv_scale = np.float32(_number(material, "uvScale"))
    world_u = world_x * uv_scale
    world_v = world_y * uv_scale

    ripple_tiling = np.float32(_number(material, "rippleTilingMultiplier"))
    ripple_pan = _vector(material, "ripplePan", 2) * np.float32(time_seconds)
    ripple_u = world_u * ripple_tiling
    ripple_v = world_v * ripple_tiling
    ripple_u += ripple_pan[0]
    ripple_v += ripple_pan[1]
    ripple = _sample_repeat_nearest(
        ripple_texture,
        ripple_u,
        ripple_v,
        1,
    )[:, 0]
    # The imported graph never connects its normal/detail branches to an output.
    # Their texture parameters remain part of the direct material signature, but
    # evaluating those dead branches cannot affect any returned channel.

    depth_lerp = world_y.copy()
    depth_lerp *= np.float32(
        0.125 * _number(material, "depthBlendStrength")
    )
    depth_lerp += np.float32(0.5)
    np.clip(depth_lerp, 0.0, 1.0, out=depth_lerp)
    shallow = _vector(material, "shallowColor", 4)
    deep = _vector(material, "deepColor", 4)
    color = depth_lerp[:, None] * (deep[:3] - shallow[:3])
    color += shallow[:3]
    color += (ripple - np.float32(0.5))[:, None] * np.float32(
        _number(material, "rippleAmount")
    )

    edge_sheen = np.abs(
        globals_xy[:, 0] / np.float32(framebuffer_size[0]) - np.float32(0.5)
    )
    vertical_edge = np.abs(
        globals_xy[:, 1] / np.float32(framebuffer_size[1]) - np.float32(0.5)
    )
    np.maximum(edge_sheen, vertical_edge, out=edge_sheen)
    edge_sheen *= np.float32(2.0)
    np.clip(edge_sheen, 0.0, 1.0, out=edge_sheen)
    np.power(
        edge_sheen,
        np.float32(_number(material, "sheenSharpness")),
        out=edge_sheen,
    )
    tint = _vector(material, "tint", 4)
    color += edge_sheen[:, None] * np.float32(
        _number(material, "sheenStrength")
    )
    np.clip(color, 0.0, 1.0, out=color)
    color *= tint[:3]

    alpha = depth_lerp.copy()
    alpha -= np.float32(0.5)
    alpha *= np.float32(_number(material, "alphaDepthStrength"))
    alpha += mask
    np.clip(alpha, 0.0, 1.0, out=alpha)
    alpha *= np.float32(_number(material, "overallAlpha") * tint[3])
    visible = mask >= _number(material, "alphaCutoff")
    if not bool(np.all(visible)):
        alpha[~visible] = 0.0
        color[~visible] = 0.0
    if material.get("premultiplyOutput") is True:
        color *= alpha[:, None]
    elif material.get("premultiplyOutput") is not False:
        raise ValueError("Water premultiplyOutput must be boolean")
    output = np.empty((count, 4), dtype=np.float32)
    output[:, :3] = color
    output[:, 3] = alpha
    output *= np.float32(255.0)
    np.rint(output, out=output)
    np.clip(output, 0.0, 255.0, out=output)
    return output.astype(np.uint8)


def _rgba_surface(values: np.ndarray) -> pygame.Surface:
    height, width, channels = values.shape
    if channels != 4:
        raise ValueError("Water Surface data must be row-major RGBA")
    return pygame.image.frombuffer(values, (width, height), "RGBA")


def _support_pixels(width: int, height: int) -> np.ndarray:
    """Build sample-local pixels for one Water calculation."""
    local_x, local_y = np.meshgrid(
        np.arange(width, dtype=np.float32),
        np.arange(height, dtype=np.float32),
        indexing="ij",
    )
    values = np.column_stack((local_x.ravel(), local_y.ravel()))
    values.setflags(write=False)
    return values


def render_water_batch(
    *,
    mask_surface: pygame.Surface,
    ripple_texture: np.ndarray,
    normal_texture: np.ndarray,
    supports: Sequence[WaterSupportInput],
    framebuffer_size: tuple[int, int],
    tile_width_px: float,
    render_scale: float,
    time_seconds: float,
    material: Mapping[str, object],
) -> WaterBatchOutput:
    """Evaluate one owner chunk once and scatter it into painter-slot Surfaces."""
    if not supports:
        raise ValueError("Water batch must contain at least one support")
    width, height = mask_surface.get_size()
    mask = pygame.surfarray.array_alpha(mask_surface).astype(np.float32) / 255.0
    active_2d = mask >= _number(material, "alphaCutoff")
    active = active_2d.ravel()
    local = _support_pixels(width, height)[active]
    per_support = int(active.sum())
    if per_support == 0:
        raise ValueError("Water mask has no pixels above its alpha cutoff")
    input_pixels = np.tile(local, (len(supports), 1))
    origins = np.repeat(
        np.asarray([support.source_origin_px for support in supports], dtype=np.float32),
        per_support,
        axis=0,
    )
    destinations = np.repeat(
        np.asarray([support.destination_px for support in supports], dtype=np.float32),
        per_support,
        axis=0,
    )
    global_pixels = destinations + input_pixels
    rgba = shade_water_packed(
        mask_alpha=np.tile(mask.ravel()[active], len(supports)),
        input_pixels=input_pixels,
        source_origins_px=origins,
        global_framebuffer_pixels=global_pixels,
        framebuffer_size=framebuffer_size,
        tile_width_px=tile_width_px,
        render_scale=render_scale,
        time_seconds=time_seconds,
        ripple_texture=ripple_texture,
        normal_texture=normal_texture,
        material=material,
    ).reshape((len(supports), per_support, 4))
    treated_rgb = rgba[:, :, :3].astype(np.float32)
    treated_rgb *= np.asarray(
        [support.multiplier for support in supports],
        dtype=np.float32,
    )[:, None, :]
    np.clip(treated_rgb, 0, 255, out=treated_rgb)
    rgba[:, :, :3] = treated_rgb.astype(np.uint8)
    active_x, active_y = np.nonzero(active_2d)
    crop_x = int(active_x.min())
    crop_y = int(active_y.min())
    crop_width = int(active_x.max()) - crop_x + 1
    crop_height = int(active_y.max()) - crop_y + 1
    cropped_indices = (
        (local[:, 1].astype(np.intp) - crop_y) * crop_width
        + local[:, 0].astype(np.intp)
        - crop_x
    )
    scattered: list[pygame.Surface] = []
    scattered_destinations: list[tuple[int, int]] = []
    for index, support in enumerate(supports):
        values = np.zeros((crop_width * crop_height, 4), dtype=np.uint8)
        values[cropped_indices] = rgba[index]
        values = values.reshape((crop_height, crop_width, 4))
        scattered.append(_rgba_surface(values))
        scattered_destinations.append((
            support.destination_px[0] + crop_x,
            support.destination_px[1] + crop_y,
        ))
    min_x = min(support.destination_px[0] for support in supports)
    min_y = min(support.destination_px[1] for support in supports)
    max_x = max(support.destination_px[0] + width for support in supports)
    max_y = max(support.destination_px[1] + height for support in supports)
    return WaterBatchOutput(
        surfaces=tuple(scattered),
        destinations=tuple(scattered_destinations),
        evaluated_pixels=per_support * len(supports),
        destination_bounds=(min_x, min_y, max_x, max_y),
    )


__all__ = [
    "WaterBatchOutput",
    "WaterSupportInput",
    "render_water_batch",
    "shade_water_packed",
    "water_source_origin",
]
