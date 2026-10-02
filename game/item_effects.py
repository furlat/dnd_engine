"""Existing condition materials applied only to their retained owning item."""

from functools import lru_cache
from colorsys import rgb_to_hls, hls_to_rgb
from pathlib import Path
from typing import Mapping

from pydantic import BaseModel, ConfigDict, Field

from dnd.core.creature_types import DamageType

import numpy as np
import pygame

from dnd.core.item_types import ItemEffectPresentationState
from game.condition_types import ConditionRecipe, load_condition_recipes
from game.item_appearance import item_source_palettes


class ItemMaterialRecipe(BaseModel):
    """Passive received-fact selection; no gameplay or new sprite geometry."""

    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)
    behavior_id: str = Field(min_length=1)
    damage_type: DamageType
    tint_rgb: int = Field(ge=0, le=0xFFFFFF)
    bloom_strength: float = Field(ge=0, le=0.5)
    bloom_radius: int = Field(ge=0, le=3)
    priority: int = Field(ge=0, le=100)


class ItemMaterialDocument(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    version: int = Field(ge=1, le=1)
    recipes: tuple[ItemMaterialRecipe, ...]


@lru_cache(maxsize=1)
def item_material_recipes() -> tuple[ItemMaterialRecipe, ...]:
    document = ItemMaterialDocument.model_validate_json(
        (Path(__file__).parent / "data/item-materials.json").read_text())
    keys = [(row.behavior_id, row.damage_type) for row in document.recipes]
    if len(keys) != len(set(keys)):
        raise ValueError("Duplicate item material selector")
    return document.recipes


def _material_recipe(effects: tuple[ItemEffectPresentationState, ...]) -> ItemMaterialRecipe | None:
    keys = {(effect.behavior_id, effect.damage_type) for effect in effects}
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
                  category: str, base_tint: int = 0xFFFFFF) -> pygame.Surface:
    """Swap authored palette zones; preserve other colors and original alpha."""
    modifiers = [modifier for effect in effects
                 if (recipe := recipes.get(effect.behavior_id)) is not None
                 for modifier in recipe.persistent.equipmentModifiers if slot in modifier.slots]
    material = _material_recipe(effects) if slot in ("weapon", "offhand") else None
    if not modifiers and material is None and base_tint == 0xFFFFFF:
        return surface
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
        rgb = pygame.surfarray.array3d(surface)
        distance = ((rgb[..., None, :] - source_colors) ** 2).sum(axis=3)
        zone = distance.argmin(axis=2)
        matched = (distance.min(axis=2) < (255 * .1) ** 2) & (pygame.surfarray.array_alpha(surface) > 0)
        pixels = pygame.surfarray.pixels3d(result)
        pixels[matched] = targets[zone[matched]]
        del pixels
        if material is not None and material.bloom_strength:
            _bounded_bloom(result, matched, material)
    for modifier in sorted(modifiers, key=lambda row: row.priority):
        if modifier.alphaMultiplier != 1:
            alpha = pygame.surfarray.pixels_alpha(result)
            alpha[:] = np.rint(alpha * modifier.alphaMultiplier).astype(np.uint8)
            del alpha
    return result
