"""Playable scenario packages for NeuroDragon."""

from dnd.scenarios.agent_decision_training import (
    DecisionScene,
    TwoTargetDecisionScene,
    create_decision_scene,
    create_melee_only_skeleton as create_decision_melee_only_skeleton,
    create_two_target_scene,
)
from dnd.scenarios.agent_tactical_training import (
    AgentTrainingScene,
    FirstAttackAgent,
    clear_melee_attack_modifier,
    create_agent_scene,
    make_melee_attack_auto_hit,
    reset_agent_interface_state,
)
from dnd.scenarios.controller_catalogue import (
    RecordingTurnRunner,
    create_controller_pair,
    create_melee_only_skeleton as create_controller_melee_only_skeleton,
    make_turn_context,
    manhattan_distance,
    reset_controller_catalogue_state,
    start_ordered_controller_encounter,
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
    "AgentTrainingScene",
    "DecisionScene",
    "FirstAttackAgent",
    "RecordingTurnRunner",
    "TwoTargetDecisionScene",
    "clear_melee_attack_modifier",
    "create_agent_scene",
    "create_controller_pair",
    "create_controller_melee_only_skeleton",
    "create_decision_scene",
    "create_decision_melee_only_skeleton",
    "create_two_target_scene",
    "make_turn_context",
    "make_melee_attack_auto_hit",
    "manhattan_distance",
    "reset_agent_interface_state",
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
