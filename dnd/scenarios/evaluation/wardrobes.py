"""RPG wardrobe profiles shared by composed and legacy scenario settings."""

from __future__ import annotations

from collections.abc import Iterable

from dnd.blocks.equipment import Armor
from dnd.content_system.item_bindings import ItemRuntimeOrigin
from dnd.content_system.item_materialization import materialize_item
from dnd.entity import Entity
from dnd.items.armors import (
    ARMORED_BOOTS_RECIPE,
    CLOTH_SHOES_RECIPE,
    LEATHER_BOOTS_RECIPE,
)
from dnd.items.apparel_presets import (
    ACOLYTE_VESTMENTS_PRESET,
    BLUE_CLOTH_SHOES_PRESET,
    BROWN_BOOTS_PRESET,
    BROWN_LEATHER_SHOES_PRESET,
    DARK_BOOTS_PRESET,
    DARK_CLOTH_SHOES_PRESET,
    DARK_CULTIST_ROBES_PRESET,
    FARMHAND_TUNIC_PRESET,
    HEDGE_WIZARD_ROBE_PRESET,
    NECROMANCER_ROBE_PRESET,
    PEASANT_RAGS_PRESET,
    PIT_FIGHTER_WRAP_PRESET,
    PRIEST_VESTMENTS_PRESET,
    ROPE_SANDALS_PRESET,
    THIEF_GARB_PRESET,
    WIZARD_ROBE_PRESET,
)
from dnd.scenarios.evaluation.models import ApparelGrant, BestiaryArchetype


BERSERKER_WARDROBE = (
    ApparelGrant(recipe=PIT_FIGHTER_WRAP_PRESET.recipe),
    ApparelGrant(recipe=LEATHER_BOOTS_RECIPE),
)

CASTER_WARDROBES: dict[str, tuple[ApparelGrant, ...]] = {
    "arcane": (
        ApparelGrant(recipe=HEDGE_WIZARD_ROBE_PRESET.recipe),
        ApparelGrant(recipe=CLOTH_SHOES_RECIPE),
    ),
    "dark": (
        ApparelGrant(recipe=DARK_CULTIST_ROBES_PRESET.recipe),
        ApparelGrant(recipe=DARK_CLOTH_SHOES_PRESET.recipe),
    ),
    "divine": (
        ApparelGrant(recipe=PRIEST_VESTMENTS_PRESET.recipe),
        ApparelGrant(recipe=ROPE_SANDALS_PRESET.recipe),
    ),
    "necromancer": (
        ApparelGrant(recipe=NECROMANCER_ROBE_PRESET.recipe),
        ApparelGrant(recipe=DARK_CLOTH_SHOES_PRESET.recipe),
    ),
}

BESTIARY_WARDROBES: dict[BestiaryArchetype, tuple[ApparelGrant, ...]] = {
    "goblin": (
        ApparelGrant(recipe=DARK_BOOTS_PRESET.recipe),
    ),
    "goblin_archer": (
        ApparelGrant(recipe=DARK_BOOTS_PRESET.recipe),
    ),
}

_LEATHER_BOOTS = (ApparelGrant(recipe=LEATHER_BOOTS_RECIPE),)
_DARK_BOOTS = (ApparelGrant(recipe=DARK_BOOTS_PRESET.recipe),)
_ARMORED_BOOTS = (ApparelGrant(recipe=ARMORED_BOOTS_RECIPE),)

# Preserve each NPC's real armor. Only the five unarmored layered humanoids
# receive a body outfit; every humanoid receives role-sensible footwear using
# NeuroClient's exact annotated parent keys and variant IDs.
SRD_WARDROBES: dict[str, tuple[ApparelGrant, ...]] = {
    "commoner": (
        ApparelGrant(recipe=FARMHAND_TUNIC_PRESET.recipe),
        ApparelGrant(recipe=BROWN_LEATHER_SHOES_PRESET.recipe),
    ),
    "bandit": _DARK_BOOTS,
    "cultist": _DARK_BOOTS,
    "guard": _LEATHER_BOOTS,
    "tribal_warrior": _LEATHER_BOOTS,
    "kobold": (
        ApparelGrant(recipe=PEASANT_RAGS_PRESET.recipe),
        ApparelGrant(recipe=ROPE_SANDALS_PRESET.recipe),
    ),
    "acolyte": (
        ApparelGrant(recipe=ACOLYTE_VESTMENTS_PRESET.recipe),
        ApparelGrant(recipe=ROPE_SANDALS_PRESET.recipe),
    ),
    "scout": (
        ApparelGrant(recipe=BROWN_BOOTS_PRESET.recipe),
    ),
    "thug": _LEATHER_BOOTS,
    "orc": _LEATHER_BOOTS,
    "hobgoblin": _ARMORED_BOOTS,
    "gnoll": _LEATHER_BOOTS,
    "spy": (
        ApparelGrant(recipe=THIEF_GARB_PRESET.recipe),
        ApparelGrant(recipe=DARK_BOOTS_PRESET.recipe),
    ),
    "bugbear": _DARK_BOOTS,
    "berserker": _LEATHER_BOOTS,
    "bandit_captain": _DARK_BOOTS,
    "cult_fanatic": _DARK_BOOTS,
    "priest": _LEATHER_BOOTS,
    "knight": _ARMORED_BOOTS,
    "veteran": _ARMORED_BOOTS,
    "mage": (
        ApparelGrant(recipe=WIZARD_ROBE_PRESET.recipe),
        ApparelGrant(recipe=BLUE_CLOTH_SHOES_PRESET.recipe),
    ),
}


def equip_apparel(entity: Entity, grant: ApparelGrant) -> None:
    """Equip one setting-authored wardrobe item without replacing existing gear."""
    item = materialize_item(
        grant.recipe,
        entity.uuid,
        origin=ItemRuntimeOrigin.STARTER,
        expected_type=Armor,
    )
    if entity.equipment.get_item_by_slot(item.body_part) is not None:
        raise ValueError(
            f"Apparel grant {grant.recipe.ref.identity_key!r} would replace occupied {item.body_part.value!r} "
            f"slot for {entity.name!r}."
        )
    if not entity.equipment.equip(item):
        raise ValueError(
            "Equipment rejected apparel "
            f"{grant.recipe.ref.identity_key!r} for {entity.name!r}.",
        )


def equip_wardrobe(entity: Entity, grants: Iterable[ApparelGrant]) -> Entity:
    """Equip every item in one wardrobe profile and return the actor."""
    for grant in grants:
        equip_apparel(entity, grant)
    return entity
