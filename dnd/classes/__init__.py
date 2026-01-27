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
    # NOTE: HasAttacked and HasTakenDamage are now generic conditions in dnd/conditions.py
    # They are registered globally by setup_standard_actions() for ALL entities.
    # ExtraAttack feature only registers the Fighter-specific resource handler.
    extra_attack_resource_processor,
    create_extra_attack_resource_handler,
    ExtraAttack,
    ExtraAttackFeature,
    ExtraAttacksGranted,  # Marker for Action Surge compatibility

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

# Fighter factory
from dnd.classes.fighter_factory import (
    FighterConfig,
    FightingStyleChoice,
    EquipmentPreset as FighterEquipmentPreset,
    create_fighter,
    get_proficiency_bonus,
    get_extra_attacks,
    get_action_surge_uses,
    get_indomitable_uses,
    calculate_final_ability_scores,
)

# Barbarian factory
from dnd.classes.barbarian_factory import (
    BarbarianConfig,
    PrimalPathChoice,
    EquipmentPreset as BarbarianEquipmentPreset,
    create_barbarian,
    get_rage_uses,
    get_rage_damage,
    get_brutal_critical_dice,
    # Note: get_proficiency_bonus and get_extra_attacks already imported from fighter
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
    # Level 5: Extra Attack (HasAttacked/HasTakenDamage now in dnd/conditions.py)
    "extra_attack_resource_processor",
    "create_extra_attack_resource_handler",
    "ExtraAttack",
    "ExtraAttackFeature",
    "ExtraAttacksGranted",
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
    # Fighter Factory
    "FighterConfig",
    "FightingStyleChoice",
    "FighterEquipmentPreset",
    "create_fighter",
    "get_proficiency_bonus",
    "get_extra_attacks",
    "get_action_surge_uses",
    "get_indomitable_uses",
    "calculate_final_ability_scores",
    # Barbarian Factory
    "BarbarianConfig",
    "PrimalPathChoice",
    "BarbarianEquipmentPreset",
    "create_barbarian",
    "get_rage_uses",
    "get_rage_damage",
    "get_brutal_critical_dice",
]
