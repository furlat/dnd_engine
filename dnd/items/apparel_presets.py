"""Stable named references to canonical ledger-authored apparel presets."""

from __future__ import annotations

from types import MappingProxyType

from dnd.core.content.recipe_presets import ContentRecipePreset
from dnd.items.authored_variant_presets import (
    AUTHORED_ITEM_RECIPE_PRESETS_BY_PRESET_ID,
)


def _preset(preset_id: str) -> ContentRecipePreset:
    """Resolve one reviewed apparel name from the sole authored preset table."""
    return AUTHORED_ITEM_RECIPE_PRESETS_BY_PRESET_ID[preset_id]


PIT_FIGHTER_WRAP_PRESET = _preset("apparel.costume.pit_fighter_wrap")
HEDGE_WIZARD_ROBE_PRESET = _preset("apparel.robes.hedge_wizard")
DARK_CULTIST_ROBES_PRESET = _preset("apparel.robes.dark_cultist")
PRIEST_VESTMENTS_PRESET = _preset("apparel.robes.priest_vestments")
NECROMANCER_ROBE_PRESET = _preset("apparel.robes.necromancer")
ACOLYTE_VESTMENTS_PRESET = _preset("apparel.robes.acolyte_vestments")
WIZARD_ROBE_PRESET = _preset("apparel.robes.wizard")
RED_MAGE_ROBE_PRESET = _preset("apparel.robes.red_mage")
FARMHAND_TUNIC_PRESET = _preset("apparel.common_clothes.farmhand_tunic")
PEASANT_RAGS_PRESET = _preset("apparel.common_clothes.peasant_rags")
THIEF_GARB_PRESET = _preset("apparel.travelers_clothes.thief_garb")
ROPE_SANDALS_PRESET = _preset("apparel.sandals.rope")
DARK_CLOTH_SHOES_PRESET = _preset("apparel.cloth_shoes.dark")
RED_CLOTH_SHOES_PRESET = _preset("apparel.cloth_shoes.red")
BLUE_CLOTH_SHOES_PRESET = _preset("apparel.cloth_shoes.blue")
BROWN_LEATHER_SHOES_PRESET = _preset("apparel.leather_shoes.brown")
DARK_BOOTS_PRESET = _preset("apparel.leather_boots.dark")
BROWN_BOOTS_PRESET = _preset("apparel.leather_boots.brown")
STEEL_HELMET_PRESET = _preset("apparel.iron_helmet.steel")
RED_WIZARD_HAT_PRESET = _preset("apparel.wizard_hat.red")


NEURODRAGON_APPAREL_RECIPE_PRESETS: tuple[ContentRecipePreset, ...] = (
    PIT_FIGHTER_WRAP_PRESET,
    HEDGE_WIZARD_ROBE_PRESET,
    DARK_CULTIST_ROBES_PRESET,
    PRIEST_VESTMENTS_PRESET,
    NECROMANCER_ROBE_PRESET,
    ACOLYTE_VESTMENTS_PRESET,
    WIZARD_ROBE_PRESET,
    RED_MAGE_ROBE_PRESET,
    FARMHAND_TUNIC_PRESET,
    PEASANT_RAGS_PRESET,
    THIEF_GARB_PRESET,
    ROPE_SANDALS_PRESET,
    DARK_CLOTH_SHOES_PRESET,
    RED_CLOTH_SHOES_PRESET,
    BLUE_CLOTH_SHOES_PRESET,
    BROWN_LEATHER_SHOES_PRESET,
    DARK_BOOTS_PRESET,
    BROWN_BOOTS_PRESET,
    STEEL_HELMET_PRESET,
    RED_WIZARD_HAT_PRESET,
)
APPAREL_RECIPE_PRESETS_BY_ID = MappingProxyType({
    preset.ref.preset_id: preset
    for preset in NEURODRAGON_APPAREL_RECIPE_PRESETS
})
APPAREL_RECIPE_PRESETS_BY_VISUAL_VARIANT_ID = MappingProxyType({
    str(preset.recipe.parameters["visual_variant_id"]): preset
    for preset in NEURODRAGON_APPAREL_RECIPE_PRESETS
})
