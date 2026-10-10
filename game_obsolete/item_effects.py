"""Existing condition materials applied only to their retained owning item."""

from functools import lru_cache
from colorsys import rgb_to_hls, hls_to_rgb
from pathlib import Path
from typing import Mapping

import numpy as np
import pygame

from dnd.core.item_types import ItemEffectPresentationState
from game.condition_types import ConditionEquipmentModifier, ConditionRecipe, load_condition_recipes
from game.item_appearance import ItemMaterialDocument, ItemMaterialRecipe, item_source_palettes
from game.spell_palette import cached_palette, retain_palette


@lru_cache(maxsize=1)
def item_material_recipes() -> tuple[ItemMaterialRecipe, ...]:
    document = ItemMaterialDocument.model_validate_json(
        (Path(__file__).parent / "data/item-materials.json").read_text())
    return document.recipes


def _material_recipe(effects: tuple[ItemEffectPresentationState, ...]) -> ItemMaterialRecipe | None:
    keys = {(effect.behavior_id, effect.damage_type) for effect in effects if not effect.suppression_provider_uuids}
    # Coatings supersede intrinsic color; ties use authored semantic keys, never
    # UUID/order, so identical items look the same across independent lineages.
    return max((row for row in item_material_recipes() if (row.behavior_id, row.damage_type) in keys),
               key=lambda row: (row.priority, row.behavior_id, row.damage_type.value), default=None)


def _bounded_bloom(result: pygame.Surface, matched: np.ndarray, recipe: ItemMaterialRecipe) -> None:
    """Diffuse emission inside source item pixels; alpha/shadows stay intact."""
    alpha = pygame.surfarray.array_alpha(result)
    emission = matched.astype(float) * (alpha / 255)
    radius = recipe.bloom_radius
    if radius:
        padded = np.pad(emission, radius)
        emission = sum((padded[x:x + result.width, y:y + result.height]
                        for x in range(2 * radius + 1) for y in range(2 * radius + 1)),
                       np.zeros_like(emission)) / (2 * radius + 1) ** 2
    pixels = pygame.surfarray.pixels3d(result)
    color = np.array([recipe.tint_rgb >> 16 & 255, recipe.tint_rgb >> 8 & 255, recipe.tint_rgb & 255])
    emitted = pixels.astype(float) + emission[..., None] * color * recipe.bloom_strength
    pixels[matched] = np.clip(np.rint(emitted[matched]), 0, 255).astype(np.uint8)
    del pixels


@lru_cache(maxsize=1)
def item_condition_recipes() -> Mapping[str, ConditionRecipe]:
    data = Path(__file__).parent / "data"
    return load_condition_recipes(
        data / "neuroclient/source/src/render/data/animation/conditionPresentation.json",
        overrides=data / "condition-overrides.json", local=data / "condition-recipes.json")


def item_material(surface: pygame.Surface, effects: tuple[ItemEffectPresentationState, ...],
                  slot: str, recipes: Mapping[str, ConditionRecipe], *,
                  category: str, base_tint: int = 0xFFFFFF,
                  owned_modifiers: tuple[ConditionEquipmentModifier, ...] = (),
                  time_ms: float = 0., source_key: tuple[object, ...] | None = None) -> pygame.Surface:
    """Swap authored palette zones; preserve other colors and original alpha."""
    modifiers = [modifier for effect in effects
                 if not effect.suppression_provider_uuids and (recipe := recipes.get(effect.behavior_id)) is not None
                 for modifier in recipe.persistent.equipmentModifiers if slot in modifier.slots]
    modifiers.extend(modifier for modifier in owned_modifiers if slot in modifier.slots)
    material = _material_recipe(effects) if slot in ("weapon", "offhand") else None
    if not modifiers and material is None and base_tint == 0xFFFFFF:
        return surface
    # Source keys describe immutable loaded art, independent of camera/panning.
    # Animated glints remain sampled each frame; static dyes/coatings share the
    # renderer's existing byte-bounded palette cache.
    cache_key = (('item-material', source_key, category, base_tint, material, tuple(modifiers))
                 if source_key is not None and not any(row.glint is not None for row in modifiers) else None)
    if cache_key is not None and (cached := cached_palette(cache_key)) is not None:
        return cached
    result = surface.copy()
    # Applying both the item dye and coating color darkens an already dark
    # weapon twice. A coating supplies its own material color on the source art.
    tint = next((row.tintRgb for row in sorted(modifiers, key=lambda row: row.priority, reverse=True)
                 if row.tintRgb is not None), base_tint)
    if material is not None:
        tint = material.tint_rgb
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
        # Equipment occupies a small fraction of a complete body cell. Do the
        # same nearest-palette calculation only for its nontransparent pixels.
        occupied = pygame.surfarray.array_alpha(surface) > 0
        rgb = pygame.surfarray.array3d(surface)[occupied]
        distance = ((rgb[:, None, :] - source_colors) ** 2).sum(axis=2)
        zone = distance.argmin(axis=1)
        accepted = distance.min(axis=1) < (255 * .1) ** 2
        matched = np.zeros(surface.get_size(), dtype=bool)
        matched[occupied] = accepted
        pixels = pygame.surfarray.pixels3d(result)
        pixels[matched] = targets[zone[accepted]]
        del pixels
        for modifier in modifiers:
            glint = modifier.glint
            if glint is None:
                continue
            center = glint.startY + (glint.endY - glint.startY) * (time_ms % glint.periodMs) / glint.periodMs
            glow = np.exp(-((np.arange(surface.height) - center) / glint.width) ** 2) * glint.strength
            color = np.array([glint.color >> 16 & 255, glint.color >> 8 & 255, glint.color & 255])
            pixels = pygame.surfarray.pixels3d(result)
            emitted = pixels.astype(float) + glow[None, :, None] * color
            pixels[matched] = np.clip(np.rint(emitted[matched]), 0, 255).astype(np.uint8)
            del pixels
        if material is not None and material.bloom_strength:
            _bounded_bloom(result, matched, material)
    for modifier in sorted(modifiers, key=lambda row: row.priority):
        if modifier.alphaMultiplier != 1:
            alpha = pygame.surfarray.pixels_alpha(result)
            alpha[:] = np.rint(alpha * modifier.alphaMultiplier).astype(np.uint8)
            del alpha
    return retain_palette(cache_key, result) if cache_key is not None else result
