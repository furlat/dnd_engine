"""RPG wardrobe profiles shared by composed and legacy scenario settings."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Optional
from uuid import UUID

from dnd.blocks.equipment import Armor
from dnd.entity import Entity
from dnd.items.armors import (
    create_armored_boots,
    create_cloth_shoes,
    create_common_clothes,
    create_costume,
    create_leather_boots,
    create_leather_shoes,
    create_robes,
    create_sandals,
    create_travelers_clothes,
)
from dnd.scenarios.evaluation.models import ApparelGrant, BestiaryArchetype


ApparelFactory = Callable[[UUID, Optional[str], Optional[str]], Armor]


APPAREL_FACTORIES: dict[str, ApparelFactory] = {
    "armored_boots": create_armored_boots,
    "cloth_shoes": create_cloth_shoes,
    "common_clothes": create_common_clothes,
    "costume": create_costume,
    "leather_boots": create_leather_boots,
    "leather_shoes": create_leather_shoes,
    "robes": create_robes,
    "sandals": create_sandals,
    "travelers_clothes": create_travelers_clothes,
}


BERSERKER_WARDROBE = (
    ApparelGrant(item_id="costume", visual_variant_id="85000004", display_name="Pit Fighter's Wrap"),
    ApparelGrant(item_id="leather_boots"),
)

CASTER_WARDROBES: dict[str, tuple[ApparelGrant, ...]] = {
    "arcane": (
        ApparelGrant(item_id="robes", visual_variant_id="8100000b", display_name="Hedge Wizard's Robe"),
        ApparelGrant(item_id="cloth_shoes"),
    ),
    "dark": (
        ApparelGrant(item_id="robes", visual_variant_id="81000008", display_name="Dark Cultist Robes"),
        ApparelGrant(item_id="cloth_shoes", visual_variant_id="b0000003", display_name="Dark Cloth Shoes"),
    ),
    "divine": (
        ApparelGrant(item_id="robes", visual_variant_id="81000003", display_name="Priest's Vestments"),
        ApparelGrant(item_id="sandals", visual_variant_id="b0000002", display_name="Rope Sandals"),
    ),
    "necromancer": (
        ApparelGrant(item_id="robes", visual_variant_id="81000004", display_name="Necromancer's Robe"),
        ApparelGrant(item_id="cloth_shoes", visual_variant_id="b0000003", display_name="Dark Cloth Shoes"),
    ),
}

BESTIARY_WARDROBES: dict[BestiaryArchetype, tuple[ApparelGrant, ...]] = {
    "goblin": (
        ApparelGrant(item_id="leather_boots", visual_variant_id="b0000008", display_name="Dark Boots"),
    ),
    "goblin_archer": (
        ApparelGrant(item_id="leather_boots", visual_variant_id="b0000008", display_name="Dark Boots"),
    ),
}

_LEATHER_BOOTS = (ApparelGrant(item_id="leather_boots"),)
_DARK_BOOTS = (
    ApparelGrant(item_id="leather_boots", visual_variant_id="b0000008", display_name="Dark Boots"),
)
_ARMORED_BOOTS = (ApparelGrant(item_id="armored_boots"),)

# Preserve each NPC's real armor. Only the five unarmored layered humanoids
# receive a body outfit; every humanoid receives role-sensible footwear using
# NeuroClient's exact annotated parent keys and variant IDs.
SRD_WARDROBES: dict[str, tuple[ApparelGrant, ...]] = {
    "commoner": (
        ApparelGrant(item_id="common_clothes", visual_variant_id="82000001", display_name="Farmhand's Tunic"),
        ApparelGrant(item_id="leather_shoes", visual_variant_id="b0000007", display_name="Brown Leather Shoes"),
    ),
    "bandit": _DARK_BOOTS,
    "cultist": _DARK_BOOTS,
    "guard": _LEATHER_BOOTS,
    "tribal_warrior": _LEATHER_BOOTS,
    "kobold": (
        ApparelGrant(item_id="common_clothes", visual_variant_id="82000009", display_name="Peasant's Rags"),
        ApparelGrant(item_id="sandals", visual_variant_id="b0000002", display_name="Rope Sandals"),
    ),
    "acolyte": (
        ApparelGrant(item_id="robes", visual_variant_id="81000007", display_name="Acolyte's Vestments"),
        ApparelGrant(item_id="sandals", visual_variant_id="b0000002", display_name="Rope Sandals"),
    ),
    "scout": (
        ApparelGrant(item_id="leather_boots", visual_variant_id="b0000009", display_name="Brown Boots"),
    ),
    "thug": _LEATHER_BOOTS,
    "orc": _LEATHER_BOOTS,
    "hobgoblin": _ARMORED_BOOTS,
    "gnoll": _LEATHER_BOOTS,
    "spy": (
        ApparelGrant(item_id="travelers_clothes", visual_variant_id="84000006", display_name="Thief's Garb"),
        ApparelGrant(item_id="leather_boots", visual_variant_id="b0000008", display_name="Dark Boots"),
    ),
    "bugbear": _DARK_BOOTS,
    "berserker": _LEATHER_BOOTS,
    "bandit_captain": _DARK_BOOTS,
    "cult_fanatic": _DARK_BOOTS,
    "priest": _LEATHER_BOOTS,
    "knight": _ARMORED_BOOTS,
    "veteran": _ARMORED_BOOTS,
    "mage": (
        ApparelGrant(item_id="robes", visual_variant_id="81000001", display_name="Wizard's Robe"),
        ApparelGrant(item_id="cloth_shoes", visual_variant_id="b0000005", display_name="Blue Cloth Shoes"),
    ),
}


def equip_apparel(entity: Entity, grant: ApparelGrant) -> None:
    """Equip one setting-authored wardrobe item without replacing existing gear."""
    item = APPAREL_FACTORIES[grant.item_id](
        entity.uuid,
        grant.visual_variant_id,
        grant.display_name,
    )
    if entity.equipment.get_item_by_slot(item.body_part) is not None:
        raise ValueError(
            f"Apparel grant {grant.item_id!r} would replace occupied {item.body_part.value!r} "
            f"slot for {entity.name!r}."
        )
    if not entity.equipment.equip(item):
        raise ValueError(f"Equipment rejected apparel {grant.item_id!r} for {entity.name!r}.")


def equip_wardrobe(entity: Entity, grants: Iterable[ApparelGrant]) -> Entity:
    """Equip every item in one wardrobe profile and return the actor."""
    for grant in grants:
        equip_apparel(entity, grant)
    return entity
