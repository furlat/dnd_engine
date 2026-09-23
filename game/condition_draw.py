"""Pygame pixels for the original per-slot Pixi condition body filter."""

from typing import Mapping, Sequence, cast

import numpy as np
import pygame

from game.condition_types import Activity, ConditionBodyColor
from dnd.core.life_types import LifeState
from game.condition_media import ResolvedConditionLayer
from game.condition_sampling import sample_condition_media
from game.animation_types import AnimationData, Facing8
from game.animation import view_facing
from game.registered_media import registered_media_blits
from game.projection import TILE_WIDTH


# ConditionOverlayController's body visual slots: equipment participates;
# independent actor effect/slash layers and the shadow do not receive color.
CONDITION_BODY_SLOTS = frozenset((
    "body", "shoes", "legs", "mount", "chest", "belt", "hands", "offhand",
    "weapon", "weaponGlow", "backpack", "head", "beard", "helmet",
))


def load_condition_layers(layers: Sequence[ResolvedConditionLayer],
                          rows: dict[tuple[str, str, str, int], pygame.Surface]) -> None:
    """Preload selected attachments into the existing session's immutable rows."""
    for resolved in layers:
        layer = resolved.layer
        for facing, spec in resolved.media.images_by_facing.items():
            key = ("condition", layer.assetId, facing, 0)
            if key not in rows:
                rows[key] = pygame.image.load(spec.path).convert_alpha()


def compose_condition_layers(body: pygame.Surface, destination: tuple[int, int],
                             ground: tuple[float, float], facing: str, scale: float, scale_x: float,
                             layers: tuple[ResolvedConditionLayer, ...],
                             rows: Mapping[tuple[str, str, str, int], pygame.Surface],
                             *, data: AnimationData | None = None, quadrant: int = 0,
                             floor_ground: tuple[float, float] | None = None, activity: Activity = "idle",
                             attachment_anchors: Mapping[str, tuple[float, float]] | None = None,
                             life_state: LifeState = LifeState.ALIVE,
                             ) -> tuple[pygame.Surface, tuple[int, int]]:
    """Keep feet registration while joining back/body/front at one actor depth."""
    behind, front = [], []
    bounds = pygame.Rect(destination, body.size)
    for resolved in layers:
        layer = resolved.layer
        if activity not in layer.activeDuring or life_state.value not in layer.lifeStates:
            continue
        anchor = ground if layer.attachment == "body" or floor_ground is None else floor_ground
        if layer.attachment in ("head", "face"):
            if attachment_anchors is None or layer.attachment not in attachment_anchors:
                continue
            anchor = attachment_anchors[layer.attachment]
        factor = scale * TILE_WIDTH / data.rig.TILE_W if data is not None else scale
        anchor = (anchor[0] + layer.offsetX * factor * scale_x, anchor[1] + layer.offsetY * factor)
        media = resolved.media
        if media.asset_id is not None:
            assert data is not None
            viewed = (view_facing(cast(Facing8, media.world_basis), quadrant, data)
                      if media.world_basis is not None else cast(Facing8, facing))
            for sample in sample_condition_media(data, resolved):
                masks = (registered_media_blits(data, sample.removal_mask[0], "impact", sample.removal_mask[1],
                    viewed, scale=media.scale * scale * TILE_WIDTH / data.rig.TILE_W, anchor=anchor, rows={})
                    if sample.removal_mask is not None else ())
                for image, point, _ in registered_media_blits(data, sample.asset_id, "impact", sample.frame,
                        viewed, scale=media.scale * scale * TILE_WIDTH / data.rig.TILE_W,
                        anchor=anchor, rows={}, alpha=sample.alpha * layer.opacity):
                    if sample.removal_mask is not None:
                        mask = pygame.Surface(image.size, pygame.SRCALPHA)
                        for part, origin, _ in masks:
                            mask.blit(part, (origin[0] - point[0], origin[1] - point[1]))
                        image = image.copy()
                        alpha = pygame.surfarray.pixels_alpha(image)
                        alpha[:] = np.rint(alpha.astype(np.float32) * pygame.surfarray.array_alpha(mask) / 255)
                        del alpha
                    bounds.union_ip(pygame.Rect(point, image.size))
                    (behind if layer.drawOrder == "behind_body" else front).append((image, point))
            continue
        spec = resolved.media.images_by_facing[facing]
        image = rows[("condition", layer.assetId, facing, 0)]
        sy, sx = spec.scale * scale, spec.scale * scale * scale_x
        image = pygame.transform.scale(image, (max(1, round(image.width * sx)), max(1, round(image.height * sy))))
        if layer.opacity != 1.:
            image.set_alpha(round((image.get_alpha() or 255) * layer.opacity))
        point = (round(anchor[0] - spec.pivot[0] * sx), round(anchor[1] - spec.pivot[1] * sy))
        bounds.union_ip(pygame.Rect(point, image.size))
        (behind if layer.drawOrder == "behind_body" else front).append((image, point))
    result = pygame.Surface(bounds.size, pygame.SRCALPHA)
    for image, point in (*behind, (body, destination), *front):
        result.blit(image, (point[0] - bounds.x, point[1] - bounds.y))
    return result, bounds.topleft


def condition_body_color(surface: pygame.Surface, color: ConditionBodyColor) -> pygame.Surface:
    """Match Pixi tint @ saturate(s - 1) @ brightness, preserving alpha.

    Pixi's saturation matrix uses the equal-channel mean, not luminance.
    AnimatedEntity adds this filter after the slot's normal tint/color policy.
    """
    image = surface.copy()
    pixels = pygame.surfarray.pixels3d(image)
    rgb = pixels.astype(np.float32)
    if abs(color.saturation - 1) > .001:
        rgb = rgb * color.saturation + rgb.mean(axis=2, keepdims=True) * (1 - color.saturation)
    if color.tintRgb is not None:
        tint = np.array((color.tintRgb >> 16 & 255, color.tintRgb >> 8 & 255,
                         color.tintRgb & 255), dtype=np.float32) / 255
        rgb *= tint
    if abs(color.brightness - 1) > .001:
        rgb *= color.brightness
    pixels[:] = np.clip(np.rint(rgb), 0, 255).astype(np.uint8)
    del pixels
    return image
