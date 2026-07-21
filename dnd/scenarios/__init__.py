"""Playable scenario packages for NeuroDragon."""

from dnd.scenarios.controller_catalogue import (
    create_controller_pair,
    create_melee_only_skeleton as create_controller_melee_only_skeleton,
    make_turn_context,
    manhattan_distance,
    reset_controller_catalogue_state,
    start_ordered_controller_encounter,
)
from dnd.scenarios.ai_validation_arenas import (
    ValidationArena,
    ValidationArenaSpec,
    create_ai_validation_arena,
    create_caster_crossfire_arena,
    create_goblin_water_skirmish_arena,
    create_skeleton_anti_aoe_split_arena,
    create_standard_skeleton_door_arena,
    list_ai_validation_arena_specs,
    reset_ai_validation_arena_state,
)
from dnd.scenarios.gatehouse import (
    GatehouseScenario,
    ScenarioHumanController,
    ScenarioPassController,
    add_melee_auto_hit,
    create_gatehouse_scenario,
    remove_melee_auto_hit,
    reset_playable_scenario_state,
)

__all__ = [
    "ValidationArena",
    "ValidationArenaSpec",
    "create_ai_validation_arena",
    "create_caster_crossfire_arena",
    "create_controller_pair",
    "create_controller_melee_only_skeleton",
    "create_goblin_water_skirmish_arena",
    "create_skeleton_anti_aoe_split_arena",
    "create_standard_skeleton_door_arena",
    "list_ai_validation_arena_specs",
    "make_turn_context",
    "manhattan_distance",
    "reset_ai_validation_arena_state",
    "reset_controller_catalogue_state",
    "start_ordered_controller_encounter",
    "GatehouseScenario",
    "ScenarioHumanController",
    "ScenarioPassController",
    "add_melee_auto_hit",
    "create_gatehouse_scenario",
    "remove_melee_auto_hit",
    "reset_playable_scenario_state",
]
