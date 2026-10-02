"""Selected roster gear composed from existing cold bases, without actor rules."""
from dataclasses import replace
from types import MappingProxyType
from typing import Mapping

from dnd.content.items.authored_item_definitions import AUTHORED_WEAPON_DEFINITIONS, WeaponDefinition, WearableDefinition, AuthoredItemDefinition
from dnd.content.items.item_composition import named_item, with_extra_damage, with_weapon_bonus
from dnd.core.creature_types import DamageType
from dnd.core.equipment_types import WeaponProperty, BodyPart
from dnd.core.item_properties import AdditionalDamage


# Selected family definitions, not a Cartesian product of all bases and tiers.
# Two identical elite scimitars are two physical instances of the same definition.
_PSYCHIC_SELECTIONS = (
    ("weapon.roster.psychic_scimitar", "Mindreaver Scimitar", "weapon.scimitar", 2, "Scimitar", "roster.04d42f39cbd2"),
    ("weapon.roster.psychic_greataxe", "Mindcleaver Greataxe", "weapon.greataxe", 2, "Greataxe", "roster.e2e34fdcf4d3"),
    ("weapon.roster.psychic_trident", "Thoughtpiercer Trident", "weapon.trident", 2, "Trident", "roster.26ceabf2b7f3"),
    ("weapon.roster.psychic_longsword", "Mindreaver Longsword", "weapon.longsword", 2, "Longsword", "roster.d7ebed5af586"),
    ("weapon.roster.psychic_longsword_greater", "Soulbreaker Longsword", "weapon.longsword", 3, "Longsword", "roster.d7ebed5af586"),
)

ROSTER_WEAPON_DEFINITIONS: Mapping[str, WeaponDefinition] = MappingProxyType({
    item_id: replace(
        named_item(
            with_extra_damage(
                with_weapon_bonus(AUTHORED_WEAPON_DEFINITIONS[base_id], bonus=tier),
                packet=AdditionalDamage(6, tier, DamageType.PSYCHIC),
            ),
            item_id=item_id,
            name=name,
        ),
        description=f"A magical {tier:+d} weapon that deals an additional {tier}d6 psychic damage on a hit.",
        is_magical=True,
        visual_item_name=visual_name,
        visual_variant_id=variant,
        tags=(*AUTHORED_WEAPON_DEFINITIONS[base_id].tags, "roster", "magical", "psychic"),
    )
    for item_id, name, base_id, tier, visual_name, variant in _PSYCHIC_SELECTIONS
})

ROSTER_EMBER_DEFINITIONS: Mapping[str, WeaponDefinition] = MappingProxyType({
    item_id: replace(named_item(
        with_extra_damage(AUTHORED_WEAPON_DEFINITIONS[base_id],
                          packet=AdditionalDamage(6, 1, DamageType.FIRE)),
        item_id=item_id, name=name),
        description="A magical weapon that deals an additional 1d6 fire damage on a hit.",
        is_magical=True, visual_item_name=visual_name, visual_variant_id=variant,
        tags=(*AUTHORED_WEAPON_DEFINITIONS[base_id].tags, "roster", "magical", "ember"))
    for item_id, name, base_id, visual_name, variant in (
        ("weapon.roster.ember_longsword", "Ember Longsword", "weapon.longsword", "Longsword", "roster.8fce8f4404d0"),
        ("weapon.roster.ember_greatsword", "Ember Greatsword", "weapon.greatsword", "Greatsword", "roster.b25b1c9931b1"),
    )
})


ROSTER_MAUL_DEFINITION = WeaponDefinition(
    "weapon.maul", "Maul", "A heavy two-handed hammer.",
    ("heavy", "martial", "melee", "weapon"),
    damage_die=6, damage_dice_count=2, damage_type=DamageType.BLUDGEONING,
    properties=(WeaponProperty.HEAVY, WeaponProperty.TWO_HANDED, WeaponProperty.MARTIAL),
    # Shared original hammer geometry is explicitly approximate; native rules remain Maul.
    visual_item_name="Maul", visual_variant_id="roster.06ceb223da45",
)


# Ordinary carried gear uses the existing hand/attack path. Specialist focus,
# ammunition, loading, tool checks and container contents are deliberately deferred.
ROSTER_CARRIED_DEFINITIONS: Mapping[str, WeaponDefinition] = MappingProxyType({
    "focus.wand": WeaponDefinition("focus.wand", "Wand",
        "An ordinary carried wand; no charges or focus-component mechanics.",
        ("gear", "focus", "carried"), visual_item_name="Wand"),
    "tool.crowbar": WeaponDefinition("tool.crowbar", "Crowbar",
        "An ordinary held crowbar; tool-check bonuses are not implemented.",
        ("gear", "tool", "carried"), visual_item_name="Crowbar"),
    "tool.banner": WeaponDefinition("tool.banner", "Banner",
        "An ordinary two-handed banner and pole, without an aura or combat buff.",
        ("gear", "banner", "carried"), properties=(WeaponProperty.TWO_HANDED,),
        visual_item_name="Banner"),
    "weapon.musket": WeaponDefinition("weapon.musket", "Musket",
        "A two-handed ranged weapon. Ammunition and Loading mechanics are deferred.",
        ("gear", "weapon", "ranged"), damage_die=12, damage_type=DamageType.PIERCING,
        properties=(WeaponProperty.RANGED, WeaponProperty.TWO_HANDED, WeaponProperty.MARTIAL),
        range_kind="range", normal_range_feet=40, long_range_feet=120,
        visual_item_name="Musket"),
})

ROSTER_GEAR_DEFINITIONS: Mapping[str, WearableDefinition] = MappingProxyType({
    "gear.quiver": WearableDefinition("gear.quiver", "Quiver",
        "An ordinary worn quiver; arrows remain in the actor's inventory.",
        ("gear", "backpack", "quiver"), wearable_kind="accessory",
        body_part=BodyPart.BACKPACK, visual_item_name="Quiver"),
    "gear.canister": WearableDefinition("gear.canister", "Back Canister",
        "An ordinary strapped canister without a volatile payload or storage bonus.",
        ("gear", "backpack", "canister"), wearable_kind="accessory",
        body_part=BodyPart.BACKPACK, visual_item_name="Back Canister"),
})

ROSTER_INVENTORY_DEFINITIONS: Mapping[str, AuthoredItemDefinition] = MappingProxyType({
    "gear.saddle": AuthoredItemDefinition("gear.saddle", "Saddle and Tack",
        "An ordinary inventory possession; mounted equipment behavior is deferred.",
        ("gear", "saddle", "tack"), visual_item_name="Saddle and Tack"),
})
