"""
Utility functions for the D&D engine.

This module provides reusable utilities for testing, debugging, and scripting.
"""

from dnd.utils.test_utils import (
    reset_combat_state,
    setup_combat_arena,
    force_attack_hit,
    force_attack_miss,
    force_attack_crit,
    force_spell_attack_hit,
    force_spell_attack_crit,
    remove_attack_modifier,
    remove_spell_attack_modifier,
    run_turn_until_end,
    deal_damage_to,
    heal_entity,
    get_hp,
    get_max_hp,
    set_hp,
    get_position,
    move_entity,
    has_condition,
    count_conditions,
    get_save_natural_roll,
    print_combat_state,
)

__all__ = [
    "reset_combat_state",
    "setup_combat_arena",
    "force_attack_hit",
    "force_attack_miss",
    "force_attack_crit",
    "force_spell_attack_crit",
    "remove_attack_modifier",
    "remove_spell_attack_modifier",
    "run_turn_until_end",
    "deal_damage_to",
    "heal_entity",
    "get_hp",
    "get_max_hp",
    "set_hp",
    "get_position",
    "move_entity",
    "has_condition",
    "count_conditions",
    "get_save_natural_roll",
    "print_combat_state",
]
