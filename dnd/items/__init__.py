"""D&D 5e Item Factories

This module provides factory functions for creating D&D 5e weapons and armor.
"""

from dnd.items.weapons import (
    # Simple Melee
    create_club,
    create_dagger,
    create_handaxe,
    create_javelin,
    create_mace,
    create_quarterstaff,
    create_spear,
    # Simple Ranged
    create_light_crossbow,
    create_shortbow,
    # Martial Melee
    create_battleaxe,
    create_greataxe,
    create_greatsword,
    create_longsword,
    create_rapier,
    create_scimitar,
    create_shortsword,
    create_warhammer,
    # Martial Ranged
    create_longbow,
    create_heavy_crossbow,
    # Arcane
    create_arcane_staff,
)

from dnd.items.armors import (
    # Light
    create_padded_armor,
    create_leather_armor,
    create_studded_leather,
    # Medium
    create_hide_armor,
    create_chain_shirt,
    create_scale_mail,
    create_breastplate,
    create_half_plate,
    # Heavy
    create_ring_mail,
    create_chain_mail,
    create_splint_armor,
    create_plate_armor,
    # Shield
    create_shield,
    create_wooden_shield,
)

# Weapon lookup by name (for presets)
WEAPONS = {
    # Simple Melee
    "club": create_club,
    "dagger": create_dagger,
    "handaxe": create_handaxe,
    "javelin": create_javelin,
    "mace": create_mace,
    "quarterstaff": create_quarterstaff,
    "spear": create_spear,
    # Simple Ranged
    "light_crossbow": create_light_crossbow,
    "shortbow": create_shortbow,
    # Martial Melee
    "battleaxe": create_battleaxe,
    "greataxe": create_greataxe,
    "greatsword": create_greatsword,
    "longsword": create_longsword,
    "rapier": create_rapier,
    "scimitar": create_scimitar,
    "shortsword": create_shortsword,
    "warhammer": create_warhammer,
    # Martial Ranged
    "longbow": create_longbow,
    "heavy_crossbow": create_heavy_crossbow,
}

ARMORS = {
    # Light
    "padded": create_padded_armor,
    "leather": create_leather_armor,
    "studded_leather": create_studded_leather,
    # Medium
    "hide": create_hide_armor,
    "chain_shirt": create_chain_shirt,
    "scale_mail": create_scale_mail,
    "breastplate": create_breastplate,
    "half_plate": create_half_plate,
    # Heavy
    "ring_mail": create_ring_mail,
    "chain_mail": create_chain_mail,
    "splint": create_splint_armor,
    "plate": create_plate_armor,
}

SHIELDS = {
    "shield": create_shield,
    "wooden_shield": create_wooden_shield,
}

__all__ = [
    # Simple Melee
    "create_club",
    "create_dagger",
    "create_handaxe",
    "create_javelin",
    "create_mace",
    "create_quarterstaff",
    "create_spear",
    # Simple Ranged
    "create_light_crossbow",
    "create_shortbow",
    # Martial Melee
    "create_battleaxe",
    "create_greataxe",
    "create_greatsword",
    "create_longsword",
    "create_rapier",
    "create_scimitar",
    "create_shortsword",
    "create_warhammer",
    # Martial Ranged
    "create_longbow",
    "create_heavy_crossbow",
    # Arcane
    "create_arcane_staff",
    # Light Armor
    "create_padded_armor",
    "create_leather_armor",
    "create_studded_leather",
    # Medium Armor
    "create_hide_armor",
    "create_chain_shirt",
    "create_scale_mail",
    "create_breastplate",
    "create_half_plate",
    # Heavy Armor
    "create_ring_mail",
    "create_chain_mail",
    "create_splint_armor",
    "create_plate_armor",
    # Shields
    "create_shield",
    "create_wooden_shield",
    # Lookup dicts
    "WEAPONS",
    "ARMORS",
    "SHIELDS",
]
