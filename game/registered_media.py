"""Registered atlas parts transformed around one authored pivot."""

from functools import lru_cache
from dataclasses import dataclass
from math import cos, degrees, sin
from typing import Literal, Mapping

import pygame
import numpy as np

from game.animation_types import AnimationData, Facing8, ProjectileSprite
from game.projectile_media import projectile_frame_layers


@lru_cache(maxsize=128)
def registered_material(asset_id: str, alpha: float) -> ProjectileSprite:
    return ProjectileSprite(renderer="sprite_projectile", assetId=asset_id, alpha=alpha,
        tint=0xFFFFFF, blendMode="normal", offsetX=0, offsetY=0,
        geometryComposition="replace_geometry", mediaFailurePolicy="fail_transaction")



@dataclass(frozen=True, slots=True)
class RegisteredMediaSample:
    image: pygame.Surface
    destination: tuple[int, int]
    blend: int
    footpoints: np.ndarray | None = None
    positions: np.ndarray | None = None
    ownership: np.ndarray | None = None
    vertical_scale: float = 1


def _nearest_indices(source_size: int, output_size: int) -> np.ndarray:
    """Match SDL's 16-bit fixed-point center sampling, including its ties."""
    step = (source_size << 16) // output_size
    return (np.arange(output_size, dtype=np.int64) * step + step // 2) >> 16


def registered_media_samples(data: AnimationData, asset_id: str,
                           phase: Literal["cast", "travel", "impact"], frame: int,
                           facing: Facing8, *, scale: float, anchor: tuple[float, float],
                           rows: Mapping[tuple[str, int], pygame.Surface],
                           alpha: float = 1.0, rotation: float = 0.0, zoom: float = 1.0,
                           ) -> tuple[RegisteredMediaSample, ...]:
    """Scale is the final pixel factor; rotation is clockwise screen radians.

    Sparse rectangles retain their offsets in the source canvas. Transform each
    rectangle about the common registered pivot without allocating that canvas.
    """
    asset = data.projectile_assets[asset_id]
    pivot = (asset.anchorsByFacing or {}).get(facing, asset.anchor)
    asset_pivot = pivot.x * asset.frame.width, pivot.y * asset.frame.height
    layers = projectile_frame_layers(data, asset, phase, frame, facing,
                                    registered_material(asset_id, alpha), rows)
    result = []
    for layer in layers:
        image = layer.image
        footpoint_image = layer.footpoint.image if layer.footpoint is not None else None
        if not rotation:
            # All parts share the registered canvas edges. Independent rounding
            # of each band's size creates transparent seams at fractional zoom.
            left = round(anchor[0] + (layer.offset[0] - asset_pivot[0]) * scale)
            top = round(anchor[1] + (layer.offset[1] - asset_pivot[1]) * scale)
            right = round(anchor[0] + (layer.offset[0] + image.width - asset_pivot[0]) * scale)
            bottom = round(anchor[1] + (layer.offset[1] + image.height - asset_pivot[1]) * scale)
            size, destination = (right - left, bottom - top), (left, top)
            if min(size) <= 0:
                continue
            if image.get_size() != size:
                image = pygame.transform.scale(image, size)
                if footpoint_image is not None:
                    footpoint_image = pygame.transform.scale(footpoint_image, size)
        else:
            size = max(1, round(image.width * scale)), max(1, round(image.height * scale))
            if image.get_size() != size:
                image = pygame.transform.scale(image, size)
                if footpoint_image is not None:
                    footpoint_image = pygame.transform.scale(footpoint_image, size)
            dx = (layer.offset[0] + layer.image.width / 2 - asset_pivot[0]) * scale
            dy = (layer.offset[1] + layer.image.height / 2 - asset_pivot[1]) * scale
            dx, dy = dx*cos(rotation)-dy*sin(rotation), dx*sin(rotation)+dy*cos(rotation)
            image = pygame.transform.rotate(image, -degrees(rotation))
            if footpoint_image is not None:
                footpoint_image = pygame.transform.rotate(footpoint_image, -degrees(rotation))
            destination = round(anchor[0]+dx-image.width/2), round(anchor[1]+dy-image.height/2)
        positions, ownership = None, None
        if layer.positions is not None:
            if rotation:
                raise ValueError("registered XYZ media uses authored camera banks, not residual screen rotation")
            # Use original sample identities, not reconstructed screen height.
            ix = _nearest_indices(layer.image.width, image.width)
            iy = _nearest_indices(layer.image.height, image.height)
            raw = layer.positions.coordinates[ix[:, None], iy[None, :]]
            low, high = layer.positions.bounds
            physical_scale = scale / (zoom * layer.positions.reference_pixel_scale)
            positions = (low + raw.astype(np.float32) * ((high - low) / 65535)) * (
                layer.positions.position_scale * physical_scale)
            ownership = layer.positions.ownership[ix[:, None], iy[None, :]]
            positions.setflags(write=False)
            ownership.setflags(write=False)
        footpoints = None
        if footpoint_image is not None:
            assert layer.footpoint is not None
            rgba = np.frombuffer(pygame.image.tobytes(footpoint_image, "RGBA"), dtype=np.uint8).reshape(
                image.height, image.width, 4).transpose(1, 0, 2).astype(np.uint16)
            packed = np.stack((rgba[:, :, 0] * 256 + rgba[:, :, 1],
                               rgba[:, :, 2] * 256 + rgba[:, :, 3]), axis=2)
            low, high = layer.footpoint.bounds
            footpoints = low + packed.astype(np.float32) * ((high - low) / 65535)
            footpoints.setflags(write=False)
        result.append(RegisteredMediaSample(image, destination, layer.blend, footpoints,
            positions, ownership, layer.positions.vertical_scale if layer.positions is not None else 1))
    return tuple(result)


def registered_media_blits(data: AnimationData, asset_id: str,
                           phase: Literal["cast", "travel", "impact"], frame: int,
                           facing: Facing8, *, scale: float, anchor: tuple[float, float],
                           rows: Mapping[tuple[str, int], pygame.Surface],
                           alpha: float = 1.0, rotation: float = 0.0,
                           ) -> tuple[tuple[pygame.Surface, tuple[int, int], int], ...]:
    """Existing color-only interface over the same registered sample placement."""
    return tuple((sample.image, sample.destination, sample.blend)
        for sample in registered_media_samples(data, asset_id, phase, frame, facing,
            scale=scale, anchor=anchor, rows=rows, alpha=alpha, rotation=rotation))
