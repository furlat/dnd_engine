"""
D&D 5e Character Classes

Each class is implemented as a collection of conditions that can be applied to entities.
"""

from dnd.classes.fighter import (
    # ==========================================================================
    # Dice manipulation - core utility
    # ==========================================================================
    create_modified_dice_roll,

    # ==========================================================================
    # Level 1: Fighting Styles
    # ==========================================================================
    FightingStyleArchery,
    FightingStyleDefense,
    defense_ac_check,
    FightingStyleDueling,
    dueling_damage_check,
    GreatWeaponFighting,
    great_weapon_fighting_processor,
    FightingStyleProtection,
    create_protection_handler,
    protection_processor,
    FightingStyleTwoWeaponFighting,
    twf_off_hand_melee_ability_bonus,
    twf_off_hand_ranged_ability_bonus,

    # ==========================================================================
    # Level 1: Second Wind
    # ==========================================================================
    SecondWind,
    SecondWindFeature,

    # ==========================================================================
    # Level 2: Action Surge
    # ==========================================================================
    ActionSurging,
    ActionSurge,
    ActionSurgeFeature,

    # ==========================================================================
    # Level 3: Champion - Improved Critical
    # ==========================================================================
    ImprovedCritical,

    # ==========================================================================
    # Level 5: Extra Attack
    # ==========================================================================
    HasAttacked,
    has_attacked_processor,
    create_has_attacked_handler,
    ExtraAttack,
    ExtraAttackFeature,

    # ==========================================================================
    # Level 9: Indomitable
    # ==========================================================================
    Indomitable,
    create_indomitable_handler,
    indomitable_processor,

    # ==========================================================================
    # Level 15: Champion - Superior Critical
    # ==========================================================================
    SuperiorCritical,

    # ==========================================================================
    # Level 18: Champion - Survivor
    # ==========================================================================
    Survivor,
    create_survivor_handler,
    survivor_processor,
)

# Dice utilities - test/reference implementations
from dnd.classes.dice_processor_utils import (
    maximize_all,
    minimize_all,
    set_all_to,
    substitute_value,
    floor_results,
    ceiling_results,
    reroll_below_and_substitute,
    reroll_below_keep_best,
    reroll_ones_once,
)

__all__ = [
    # Dice manipulation - core utility
    "create_modified_dice_roll",
    # Dice manipulation - test/reference utilities
    "maximize_all",
    "minimize_all",
    "set_all_to",
    "substitute_value",
    "floor_results",
    "ceiling_results",
    "reroll_below_and_substitute",
    "reroll_below_keep_best",
    "reroll_ones_once",
    # Level 1: Fighting Styles
    "FightingStyleArchery",
    "FightingStyleDefense",
    "defense_ac_check",
    "FightingStyleDueling",
    "dueling_damage_check",
    "GreatWeaponFighting",
    "great_weapon_fighting_processor",
    "FightingStyleProtection",
    "create_protection_handler",
    "protection_processor",
    "FightingStyleTwoWeaponFighting",
    "twf_off_hand_melee_ability_bonus",
    "twf_off_hand_ranged_ability_bonus",
    # Level 1: Second Wind
    "SecondWind",
    "SecondWindFeature",
    # Level 2: Action Surge
    "ActionSurging",
    "ActionSurge",
    "ActionSurgeFeature",
    # Level 3: Champion - Improved Critical
    "ImprovedCritical",
    # Level 5: Extra Attack
    "HasAttacked",
    "has_attacked_processor",
    "create_has_attacked_handler",
    "ExtraAttack",
    "ExtraAttackFeature",
    # Level 9: Indomitable
    "Indomitable",
    "create_indomitable_handler",
    "indomitable_processor",
    # Level 15: Champion - Superior Critical
    "SuperiorCritical",
    # Level 18: Champion - Survivor
    "Survivor",
    "create_survivor_handler",
    "survivor_processor",
]
