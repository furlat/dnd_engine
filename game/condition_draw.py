"""Pygame pixels for the original per-slot Pixi condition body filter."""

import numpy as np
import pygame

from game.condition_types import ConditionBodyColor


# ConditionOverlayController's body visual slots: equipment participates;
# independent actor effect/slash layers and the shadow do not receive color.
CONDITION_BODY_SLOTS = frozenset((
    "body", "shoes", "legs", "mount", "chest", "belt", "hands", "offhand",
    "weapon", "weaponGlow", "backpack", "head", "beard", "helmet",
))


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
