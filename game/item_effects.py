"""Existing condition materials applied only to their retained owning item."""

from functools import lru_cache
from colorsys import rgb_to_hls, hls_to_rgb
from pathlib import Path
from typing import Mapping

import numpy as np
import pygame

from dnd.core.item_types import ItemEffectPresentationState
from game.condition_types import ConditionRecipe, load_condition_recipes
from game.item_appearance import item_source_palettes


@lru_cache(maxsize=1)
def item_condition_recipes() -> Mapping[str, ConditionRecipe]:
    data = Path(__file__).parent / "data"
    return load_condition_recipes(
        data / "neuroclient/source/src/render/data/animation/conditionPresentation.json",
        overrides=data / "condition-overrides.json", local=data / "condition-recipes.json")


def item_material(surface: pygame.Surface, effects: tuple[ItemEffectPresentationState, ...],
                  slot: str, recipes: Mapping[str, ConditionRecipe], *,
                  category: str, base_tint: int = 0xFFFFFF) -> pygame.Surface:
    """Swap authored palette zones; preserve other colors and original alpha."""
    modifiers = [modifier for effect in effects
                 if (recipe := recipes.get(effect.behavior_id)) is not None
                 for modifier in recipe.persistent.equipmentModifiers if slot in modifier.slots]
    if not modifiers and base_tint == 0xFFFFFF:
        return surface
    result = surface.copy()
    # Applying both the item dye and coating color darkens an already dark
    # weapon twice. A coating supplies its own material color on the source art.
    tint = next((row.tintRgb for row in sorted(modifiers, key=lambda row: row.priority, reverse=True)
                 if row.tintRgb is not None), base_tint)
    if tint != 0xFFFFFF:
        palette = item_source_palettes().get(category)
        if palette is None:
            raise ValueError(f"Missing item color-swap palette: {category}")
        source_colors = np.array([((color >> 16) & 255, (color >> 8) & 255, color & 255)
                                  for color in palette], dtype=float)
        # HLS expects normalized channels. Shades are discrete replacements,
        # based on the authored zone lightness offsets, never pixel tinting.
        hue, lightness, saturation = rgb_to_hls((tint >> 16 & 255) / 255,
                                               (tint >> 8 & 255) / 255, (tint & 255) / 255)
        source_lightness = [(max(color) + min(color)) / 510 for color in source_colors]
        targets = np.array([hls_to_rgb(hue, np.clip(lightness + level - source_lightness[0], 0, 1), saturation)
                            for level in source_lightness]) * 255
        for modifier in sorted(modifiers, key=lambda row: row.priority):
            gray = targets.mean(axis=1, keepdims=True)
            targets = (gray + (targets - gray) * modifier.saturation) * modifier.brightness
        targets = np.clip(np.rint(targets), 0, 255).astype(np.uint8)
        rgb = pygame.surfarray.array3d(surface)
        distance = ((rgb[..., None, :] - source_colors) ** 2).sum(axis=3)
        zone = distance.argmin(axis=2)
        matched = distance.min(axis=2) < (255 * .1) ** 2
        pixels = pygame.surfarray.pixels3d(result)
        pixels[matched] = targets[zone[matched]]
        del pixels
    for modifier in sorted(modifiers, key=lambda row: row.priority):
        if modifier.alphaMultiplier != 1:
            alpha = pygame.surfarray.pixels_alpha(result)
            alpha[:] = np.rint(alpha * modifier.alphaMultiplier).astype(np.uint8)
            del alpha
    return result
