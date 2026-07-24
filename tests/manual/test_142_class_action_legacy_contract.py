"""Exact legacy dispositions and restored class/action regressions.

The archived scripts in this slice used custom runners, print-only checks, and
several historical assumptions.  This module keeps a selector-level migration
ledger and restores the behavior that was not already covered by the maintained
engine-book suites.
"""

import ast
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

import pytest
from pydantic import ValidationError

from dnd.actions import Attack, AttackEvent, Dodge, Move, Shove, ShoveEvent
from dnd.actions_functional import execute_action, get_available_actions
from dnd.blocks.abilities import AbilityConfig, AbilityScoresConfig
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.classes.barbarian import (
    BrutalCritical,
    ExtendIntimidatingPresence,
    IntimidatingPresence,
)
from dnd.classes.barbarian_factory import (
    BarbarianConfig,
    PrimalPathChoice,
    create_barbarian,
)
from dnd.classes.fighter import (
    ActionSurge,
    ActionSurgeFeature,
    ExtraAttackFeature,
    Survivor,
)
from dnd.classes.fighter_factory import (
    FighterConfig,
    create_fighter,
    get_action_surge_uses,
    get_extra_attacks,
    get_indomitable_uses,
    get_proficiency_bonus,
)
from dnd.classes.rage import EndRage, Frenzy, FrenziedStrike, Rage
from dnd.conditions import Dashing, Grappled, Incapacitated
from dnd.core.dice import AttackOutcome
from dnd.core.equipment_types import BodyPart, WeaponSlot
from dnd.core.events import EventPhase, EventQueue, EventType, TurnEndEvent
from dnd.core.gridmap import get_map
from dnd.core.life_types import LifeState
from dnd.core.modifiers import (
    AdvantageStatus,
    DamageType,
    NumericalModifier,
    ResistanceStatus,
)
from dnd.entity import Entity, EntityConfig
from dnd.items.armors import (
    create_chain_mail,
    create_chain_shirt,
    create_leather_armor,
)
from dnd.monsters.bestiary import create_skeleton
from dnd.reactions import add_opportunity_attack_handler
from dnd.utils import (
    deal_damage_to,
    force_attack_hit,
    force_attack_miss,
    get_hp,
    reset_combat_state,
    set_hp,
)
from tests.engine_book.test_chapter_10_core_actions_combat import (
    fixed_dice,
    reset_core_action_state,
    strong_entity,
)
from tests.engine_book.test_chapter_16_class_features import (
    create_book_target,
    reset_class_feature_state,
)


THIS_FILE = "tests/manual/test_142_class_action_legacy_contract.py"
EB03_FILE = "tests/engine_book/test_chapter_03_dice_events.py"
EB06_FILE = "tests/engine_book/test_chapter_06_entity_composition.py"
EB08_FILE = "tests/engine_book/test_chapter_08_standard_conditions.py"
EB09_FILE = "tests/engine_book/test_chapter_09_action_templates_discovery.py"
EB10_FILE = "tests/engine_book/test_chapter_10_core_actions_combat.py"
EB16_FILE = "tests/engine_book/test_chapter_16_class_features.py"
EB18_FILE = "tests/engine_book/test_chapter_18_encounters_apis.py"
MANUAL15_FILE = "tests/manual/test_15_class_features.py"
ACTION_SURGE_FILE = (
    "tests/manual/test_126_action_surge_extra_attack_legacy_contract.py"
)
UNARMORED_FILE = "tests/manual/test_132_barbarian_unarmored_defense.py"
CONDITION_FILE = "tests/manual/test_141_combat_condition_legacy_contract.py"
GEOMETRY_DICE_FILE = "tests/manual/test_legacy_geometry_dice_coverage.py"


class CoverageStatus(StrEnum):
    """Disposition for one archived logical test."""

    ACTIVE = "active"
    STRENGTHENED = "strengthened"
    STALE = "stale"
    RETIRED = "retired"


@dataclass(frozen=True)
class CoverageRecord:
    """Maintained selector and rationale for one archived logical test."""

    selector: str
    status: CoverageStatus
    reason: str


def _records(
    selector: str,
    *case_names: str,
    status: CoverageStatus = CoverageStatus.STRENGTHENED,
    reason: str,
) -> dict[str, CoverageRecord]:
    """Build a concise group of exact selector-level migration records."""
    return {
        case_name: CoverageRecord(
            selector=selector,
            status=status,
            reason=reason,
        )
        for case_name in case_names
    }


NEW_SURGE = (
    f"{THIS_FILE}::"
    "test_action_surge_enforces_one_use_per_turn_and_two_use_recharge"
)
NEW_ACTION_STATE = (
    f"{THIS_FILE}::"
    "test_standard_action_duration_and_blocking_rules_remain_distinct"
)
NEW_FAST = (
    f"{THIS_FILE}::"
    "test_fast_movement_tracks_armor_transitions_dash_and_feral_cleanup"
)
NEW_RAGE = (
    f"{THIS_FILE}::"
    "test_rage_resistance_maintenance_voluntary_end_and_heavy_armor_gate"
)
NEW_FRENZY = (
    f"{THIS_FILE}::"
    "test_rage_death_and_frenzy_cleanup_do_not_leave_stale_state"
)
NEW_FRENZY_SEQUENCE = (
    f"{THIS_FILE}::"
    "test_frenzy_attack_turn_sequence_preserves_parent_child_and_costs"
)
NEW_INTIMIDATING = (
    f"{THIS_FILE}::"
    "test_intimidating_presence_save_extension_range_and_immunity"
)
NEW_BRUTAL = (
    f"{THIS_FILE}::"
    "test_brutal_critical_channels_compose_and_clean_independently"
)
NEW_FACTORY = (
    f"{THIS_FILE}::"
    "test_fighter_factory_threshold_helpers_and_validation_grid"
)
NEW_LEVEL_TWENTY_FIGHTER = (
    f"{THIS_FILE}::"
    "test_level_twenty_fighter_factory_replaces_champion_features"
)
NEW_FACTION = (
    f"{THIS_FILE}::"
    "test_faction_relationships_gate_threat_and_opportunity_attacks"
)
NEW_SHOVE_WALL = (
    f"{THIS_FILE}::"
    "test_shove_stops_before_wall_and_preserves_blocker_log"
)
NEW_SURVIVOR = (
    f"{THIS_FILE}::"
    "test_survivor_negative_constitution_and_repeated_turns"
)

EB03_CRITICAL_DICE = (
    f"{EB03_FILE}::"
    "test_eb_03_002_critical_damage_doubles_dice_and_adds_bonus_once"
)
EB03_GWF = (
    f"{EB03_FILE}::"
    "test_eb_03_013_great_weapon_fighting_filters_damage_result_events"
)
EB06_FACTIONS = (
    f"{EB06_FILE}::test_eb_06_005_factions_define_allies_and_enemies"
)
EB06_STANDARD_ACTIONS = (
    f"{EB06_FILE}::"
    "test_eb_06_007_standard_actions_register_templates_and_handlers"
)
EB06_VISIBLE_FACTIONS = (
    f"{EB06_FILE}::"
    "test_eb_06_011_visible_entities_filter_into_allies_and_enemies"
)
EB08_CONTROL = (
    f"{EB08_FILE}::"
    "test_eb_08_004_grappled_incapacitated_and_restrained_limit_actions"
)
EB08_PRONE = (
    f"{EB08_FILE}::"
    "test_eb_08_010_prone_auto_stand_handler_is_standard_action_state"
)
EB09_TEMPLATES = (
    f"{EB09_FILE}::"
    "test_eb_09_001_templates_must_be_registered_and_instantiated"
)
EB09_DISCOVERY = (
    f"{EB09_FILE}::"
    "test_eb_09_002_standard_actions_discover_self_position_and_entity_groups"
)
EB09_EXECUTE = (
    f"{EB09_FILE}::"
    "test_eb_09_003_execute_by_index_instantiates_and_applies_costs"
)
EB10_OPPORTUNITY = (
    f"{EB10_FILE}::"
    "test_eb_10_005_opportunity_attack_uses_reaction_on_step_movement"
)
EB10_DISENGAGE = (
    f"{EB10_FILE}::"
    "test_eb_10_006_disengage_prevents_opportunity_attack"
)
EB10_SHOVE_NO_OA = (
    f"{EB10_FILE}::"
    "test_eb_10_007_shove_forced_movement_does_not_trigger_opportunity_attack"
)
EB10_DEATH = (
    f"{EB10_FILE}::"
    "test_eb_10_023_default_zero_hp_uses_monster_style_death"
)
EB10_DASH = (
    f"{EB10_FILE}::test_eb_10_008_dash_damage_healing_and_death_use_events"
)
EB10_SHOVE = (
    f"{EB10_FILE}::"
    "test_eb_10_022_shove_uses_videogame_bonus_action_forced_movement"
)
EB10_SHOVE_WEIGHT = (
    f"{EB10_FILE}::"
    "test_eb_10_024_bg3_shove_range_uses_strength_and_target_weight"
)
EB16_FACTORY = (
    f"{EB16_FILE}::"
    "test_eb_16_001_factories_apply_level_gated_features_and_resources"
)
EB16_FIGHTER_RESOURCES = (
    f"{EB16_FILE}::"
    "test_eb_16_002_fighter_resources_actions_and_short_rest_recharge"
)
EB16_LUCKY = (
    f"{EB16_FILE}::test_eb_16_005_lucky_feat_resource_and_d20_processor"
)
EB16_SMITE = (
    f"{EB16_FILE}::"
    "test_eb_16_006_divine_smite_handlers_use_highest_melee_hit_slot_once"
)
EB16_CHAMPION_FACTORY = (
    f"{EB16_FILE}::"
    "test_eb_16_007_fighter_level_ten_champion_adds_distinct_second_fighting_style"
)
EB16_EXTRA_ATTACK = (
    f"{EB16_FILE}::"
    "test_eb_16_008_extra_attack_recharges_for_action_surge_attack_action"
)
EB16_EXTRA_COUNTS = (
    f"{EB16_FILE}::"
    "test_eb_16_009_extra_attack_counts_scale_at_fighter_levels_eleven_and_twenty"
)
EB16_INDOMITABLE = (
    f"{EB16_FILE}::"
    "test_eb_16_010_indomitable_rerolls_failed_saves_and_recharges_on_long_rest"
)
EB16_CRITICAL = (
    f"{EB16_FILE}::"
    "test_eb_16_011_champion_critical_thresholds_upgrade_without_stacking"
)
EB16_SURVIVOR = (
    f"{EB16_FILE}::"
    "test_eb_16_012_survivor_heals_only_at_valid_turn_start_thresholds"
)
EB16_FIGHTING_STYLES = (
    f"{EB16_FILE}::"
    "test_eb_16_013_fighting_styles_place_expected_modifiers_and_handlers"
)
EB16_HIGH_SURGE = (
    f"{EB16_FILE}::"
    "test_eb_16_014_higher_level_extra_attack_refreshes_after_action_surge"
)
EB16_BARBARIAN_FACTORY = (
    f"{EB16_FILE}::"
    "test_eb_16_015_barbarian_factory_scales_rage_brutal_critical_and_capstone"
)
EB16_SMITE_GATES = (
    f"{EB16_FILE}::"
    "test_eb_16_018_divine_smite_handler_gates_fallthrough_and_critical_dice"
)
EB16_TACTICAL_BARBARIAN = (
    f"{EB16_FILE}::"
    "test_eb_16_019_barbarian_reckless_danger_sense_and_mindless_rage_edges"
)
EB16_RAGE_EVENTS = (
    f"{EB16_FILE}::"
    "test_eb_16_020_barbarian_relentless_and_persistent_rage_events"
)
EB16_INDOMITABLE_MIGHT = (
    f"{EB16_FILE}::"
    "test_eb_16_021_barbarian_indomitable_might_recomputes_skill_check_result"
)
EB16_RETALIATION = (
    f"{EB16_FILE}::"
    "test_eb_16_022_barbarian_retaliation_reaction_attack_gates"
)
EB16_PRIMAL = (
    f"{EB16_FILE}::"
    "test_eb_16_023_barbarian_primal_champion_updates_derived_combat_surfaces"
)
EB16_SMITE_TYPES = (
    f"{EB16_FILE}::"
    "test_eb_16_024_divine_smite_creature_type_bonus_dice_and_cap"
)
EB16_LUCKY_POLICY = (
    f"{EB16_FILE}::"
    "test_eb_16_025_lucky_policy_lifecycle_and_cleanup_contract"
)
EB18_FACTION_END = (
    f"{EB18_FILE}::"
    "test_eb_18_005_check_deaths_marks_dead_and_ends_single_faction_encounter"
)
MANUAL15_FRENZY_RANGE = (
    f"{MANUAL15_FILE}::"
    "test_frenzied_strike_discovery_excludes_targets_outside_weapon_reach"
)
SURGE_INTERLEAVED = (
    f"{ACTION_SURGE_FILE}::"
    "test_action_surge_refreshes_extra_attack_after_first_batch_is_spent"
)
SURGE_LEVEL_ELEVEN = (
    f"{ACTION_SURGE_FILE}::"
    "test_level_eleven_action_surge_produces_two_three_attack_batches"
)
CONDITION_DODGE = (
    f"{CONDITION_FILE}::"
    "test_dashing_and_dodging_apply_and_clean_their_exact_modifiers"
)
MODIFIED_ROLL = (
    f"{GEOMETRY_DICE_FILE}::"
    "test_create_modified_roll_preserves_original_and_rules_metadata"
)


ACTION_SURGE_CASES = {
    **_records(
        EB16_FIGHTER_RESOURCES,
        "test_feature_setup",
        "test_basic_usage",
        "test_short_rest_recharge",
        reason="The maintained fighter feature test asserts registration, grant, spend, and short-rest recharge.",
    ),
    **_records(
        NEW_SURGE,
        "test_resource_not_available",
        "test_once_per_turn_enforcement",
        "test_level_17_two_uses",
        status=CoverageStatus.ACTIVE,
        reason="The restored deterministic regression covers zero-resource denial and two uses separated by owner turns.",
    ),
    **_records(
        SURGE_INTERLEAVED,
        "test_integration_with_extra_attack",
        reason="The maintained real-action regression proves two full level-five attack batches.",
    ),
}

AVAILABLE_ACTION_CASES = {
    **_records(
        EB09_DISCOVERY,
        "test_available_actions_basic",
        reason="Maintained discovery asserts all self, position, and entity groups with legal targets.",
    ),
    **_records(
        EB10_DASH,
        "test_dash_action",
        reason="The maintained core-action suite executes Dash through event-backed action costs.",
    ),
    **_records(
        NEW_ACTION_STATE,
        "test_dodge_action",
        "test_condition_duration_at_turn_start",
        status=CoverageStatus.ACTIVE,
        reason="The restored regression executes Dodge and proves owner-turn duration semantics.",
    ),
    **_records(
        EB10_DISENGAGE,
        "test_disengage_action",
        "test_disengage_prevents_opportunity_attack",
        reason="Maintained coverage executes Disengage and proves it suppresses the leaving-reach reaction.",
    ),
    **_records(
        EB10_OPPORTUNITY,
        "test_opportunity_attack_without_disengage",
        reason="Maintained coverage asserts the completed reaction attack and reaction spend.",
    ),
    **_records(
        EB08_PRONE,
        "test_prone_actions",
        reason="Maintained coverage proves BG3 auto-stand, owner-turn timing, and half-movement spend.",
    ),
    **_records(
        NEW_ACTION_STATE,
        "test_blocking_conditions",
        status=CoverageStatus.STALE,
        reason="The archived Incapacitated expectation incorrectly denied movement; the maintained regression preserves SRD action denial and distinct Grappled movement denial.",
    ),
    **_records(
        EB09_TEMPLATES,
        "test_action_templates",
        reason="Maintained coverage directly distinguishes templates from instantiated actions.",
    ),
    **_records(
        EB09_EXECUTE,
        "test_execute_by_index",
        reason="Maintained coverage executes a discovered index and asserts exact cost consumption.",
    ),
}

BARBARIAN_FAST_MOVEMENT_CASES = _records(
    NEW_FAST,
    "test_fast_movement_unarmored",
    "test_fast_movement_light_armor",
    "test_fast_movement_medium_armor",
    "test_fast_movement_heavy_armor",
    "test_fast_movement_equip_unequip",
    "test_fast_movement_stacks_with_base",
    status=CoverageStatus.ACTIVE,
    reason="The restored test equips light, medium, and heavy armor, asserts every live transition, and proves the current-speed Dash composition rule.",
)

BARBARIAN_FIGHTER_COMBAT_CASES = {
    **_records(
        NEW_RAGE,
        "test_rage_activation_and_benefits",
        "test_end_rage_action",
        status=CoverageStatus.ACTIVE,
        reason="The restored regression discovers and executes Rage, asserts resource/cost spend, STR-save advantage, melee damage, exact resistances, and voluntary cleanup.",
    ),
    **_records(
        NEW_FRENZY,
        "test_rage_ends_when_unconscious",
        status=CoverageStatus.ACTIVE,
        reason="The restored damage-to-death path proves rage and its Frenzied child are removed.",
    ),
    **_records(
        EB16_RAGE_EVENTS,
        "test_relentless_rage",
        reason="Maintained coverage exercises both successful and failed Relentless Rage saves through real damage.",
    ),
    **_records(
        EB16_TACTICAL_BARBARIAN,
        "test_reckless_attack_advantage",
        "test_reckless_attack_resets",
        "test_danger_sense_dex_advantage",
        "test_danger_sense_disabled_when_blinded",
        "test_mindless_rage_removes_charmed",
        "test_mindless_rage_blocks_charmed",
        reason="Maintained tactical coverage asserts all live roll surfaces, contextual gates, and cleanup.",
    ),
    **_records(
        NEW_FRENZY_SEQUENCE,
        "test_frenzy_bonus_action_attack",
        status=CoverageStatus.ACTIVE,
        reason="The restored real attack sequence executes Frenzied Strike on the following turn and asserts its exact bonus-action spend.",
    ),
    **_records(
        EB16_BARBARIAN_FACTORY,
        "test_brutal_critical_extra_dice",
        "test_brutal_critical_scaling",
        reason="Maintained factory coverage asserts melee-only Brutal Critical at every feature tier.",
    ),
    **_records(
        NEW_FAST,
        "test_fast_movement_speed_bonus",
        status=CoverageStatus.ACTIVE,
        reason="The restored armor-transition regression asserts the exact 40-foot speed.",
    ),
}

BARBARIAN_FRENZY_CASES = {
    **_records(
        NEW_FRENZY_SEQUENCE,
        "test_frenzy_activation",
        "test_frenzied_includes_raging",
        "test_frenzied_strike_available",
        "test_frenzied_strike_costs_bonus_action",
        "test_frenzy_removes_frenzied_strike",
        status=CoverageStatus.ACTIVE,
        reason="The restored sequence discovers Frenzy, asserts resource and bonus-action costs, validates the parent/child tree, executes the granted strike after turn recharge, and proves idle cleanup.",
    ),
    **_records(
        MANUAL15_FRENZY_RANGE,
        "test_frenzied_strike_validates_range",
        reason="Maintained discovery coverage excludes visible targets outside weapon reach.",
    ),
    **_records(
        NEW_FRENZY,
        "test_cannot_frenzy_heavy_armor",
        "test_no_exhaustion",
        status=CoverageStatus.ACTIVE,
        reason="The restored regression asserts the heavy-armor gate and the engine's deliberate no-exhaustion variant.",
    ),
    **_records(
        NEW_FRENZY_SEQUENCE,
        "test_frenzy_maintenance",
        status=CoverageStatus.ACTIVE,
        reason="The restored base-attack then owner-turn sequence proves both Raging and Frenzied persist after qualifying activity and cascade away after a later idle turn.",
    ),
}

BARBARIAN_MINDLESS_RAGE_CASES = _records(
    EB16_TACTICAL_BARBARIAN,
    "test_mindless_rage_blocks_charmed_while_raging",
    "test_mindless_rage_blocks_frightened_while_raging",
    "test_mindless_rage_works_with_frenzied",
    "test_mindless_rage_no_effect_when_not_raging",
    "test_mindless_rage_only_blocks_specific_conditions",
    "test_mindless_rage_after_rage_ends",
    reason="Maintained coverage proves removal, conditional immunity, unrelated-condition acceptance, and post-rage restoration.",
)

BARBARIAN_MINOR_FEATURE_CASES = {
    **_records(
        EB16_BARBARIAN_FACTORY,
        "test_feral_instinct_advantage",
        reason="Maintained factory coverage asserts initiative advantage at the correct level.",
    ),
    **_records(
        NEW_FAST,
        "test_feral_instinct_removal",
        status=CoverageStatus.ACTIVE,
        reason="The restored regression removes Feral Instinct and asserts the modifier is cleaned.",
    ),
    **_records(
        EB16_INDOMITABLE_MIGHT,
        "test_indomitable_might_minimum",
        "test_indomitable_might_only_athletics",
        reason="Maintained coverage updates both the roll and completion outcome and excludes non-Strength checks.",
    ),
    **_records(
        EB16_PRIMAL,
        "test_primal_champion_str_bonus",
        "test_primal_champion_con_bonus",
        "test_primal_champion_both_bonuses",
        "test_primal_champion_removal",
        reason="Maintained coverage asserts the capstone across every derived STR/CON surface and reversible cleanup.",
    ),
}

BARBARIAN_PERSISTENT_RAGE_CASES = _records(
    EB16_RAGE_EVENTS,
    "test_persistent_rage_prevents_inactivity_end",
    "test_without_persistent_rage_ends_on_inactivity",
    "test_persistent_rage_multiple_turns",
    "test_persistent_rage_is_marker_condition",
    "test_rage_ends_when_persistent_rage_removed",
    reason="Maintained event coverage proves marker presence, multiple-turn persistence, removal, and resumed inactivity cleanup.",
)

BARBARIAN_RAGE_CASES = {
    **_records(
        NEW_RAGE,
        "test_rage_damage_resistance",
        "test_rage_activation",
        "test_rage_benefits",
        "test_rage_maintenance_attack",
        "test_rage_maintenance_damage",
        "test_rage_ends_no_activity",
        "test_cannot_rage_heavy_armor",
        "test_equip_heavy_armor_ends_rage",
        status=CoverageStatus.ACTIVE,
        reason="The restored regression asserts exact mitigation, both maintenance markers, inactivity, voluntary cleanup, and armor gates.",
    ),
    **_records(
        f"{UNARMORED_FILE}::test_unarmored_defense_basic",
        "test_unarmored_defense",
        reason="The dedicated maintained regression uses dependency-neutral slots and exact AC arithmetic.",
    ),
    **_records(
        EB16_TACTICAL_BARBARIAN,
        "test_reckless_attack",
        "test_danger_sense",
        reason="Maintained tactical coverage asserts outgoing/incoming Reckless modifiers and contextual Danger Sense.",
    ),
}

BARBARIAN_RETALIATION_CASES = _records(
    EB16_RETALIATION,
    "test_retaliation_triggers_on_hit",
    "test_retaliation_consumes_reaction",
    "test_retaliation_no_trigger_from_distance",
    "test_retaliation_no_trigger_without_reaction",
    "test_retaliation_no_trigger_without_melee_weapon",
    "test_retaliation_only_once_per_round",
    "test_retaliation_feature_summary",
    reason="Maintained coverage exercises positive-damage, distance, reaction, weapon, repeat, handler, and cleanup gates.",
)

BARBARIAN_SRD_FEATURE_CASES = {
    **_records(
        EB10_DEATH,
        "test_death_event_fires",
        reason="Maintained lifecycle coverage asserts the completed DeathEvent and authoritative DEAD state.",
    ),
    **_records(
        NEW_FRENZY,
        "test_rage_ends_when_dying",
        status=CoverageStatus.ACTIVE,
        reason="The restored lethal-damage regression proves the complete rage tree is removed.",
    ),
    **_records(
        NEW_RAGE,
        "test_voluntary_rage_end",
        status=CoverageStatus.ACTIVE,
        reason="The restored regression executes End Rage and asserts exact cleanup.",
    ),
    **_records(
        EB16_TACTICAL_BARBARIAN,
        "test_danger_sense_contextual",
        "test_mindless_rage_suspends_existing",
        reason="Maintained coverage asserts visibility/blindness context and removal of pre-existing charm/fear.",
    ),
    **_records(
        NEW_INTIMIDATING,
        "test_extend_intimidating_presence",
        "test_intimidating_presence_distance_los",
        status=CoverageStatus.ACTIVE,
        reason="The restored regression executes extension and removes fear after the range/visibility end check.",
    ),
}

# These seven cases were already restored one-for-one before this slice.  They
# are retained here for local completeness but are not a second central overlay.
BARBARIAN_UNARMORED_ALREADY_MAPPED = {
    case_name: f"{UNARMORED_FILE}::{case_name}"
    for case_name in (
        "test_unarmored_defense_basic",
        "test_unarmored_defense_disabled_by_armor",
        "test_unarmored_defense_with_shield",
        "test_removing_armor_restores_unarmored",
        "test_unarmored_defense_high_con",
        "test_unarmored_defense_low_con",
        "test_unarmored_defense_with_cloth_armor",
    )
}

BRUTAL_CRITICAL_CASES = {
    **_records(
        NEW_BRUTAL,
        "test_default_crit_extra_dice",
        "test_brutal_critical_modifier",
        "test_separate_melee_ranged",
        status=CoverageStatus.ACTIVE,
        reason="The restored regression asserts default, general, melee-only, and reversible crit-dice channels.",
    ),
    **_records(
        EB03_CRITICAL_DICE,
        "test_dice_crit_extra_dice",
        "test_damage_get_dice",
        reason="Maintained deterministic dice coverage proves critical expansion and propagation of extra dice.",
    ),
}

DIVINE_SMITE_CASES = {
    **_records(
        EB16_SMITE_TYPES,
        "test_smite_dice_per_slot_level",
        status=CoverageStatus.STALE,
        reason="The archived skeleton target ignored the SRD undead bonus die; maintained coverage distinguishes humanoid, undead, and fiend payloads.",
    ),
    **_records(
        EB16_SMITE_GATES,
        "test_smite_crit_doubles_dice",
        status=CoverageStatus.STALE,
        reason="The archived skeleton critical count omitted the undead bonus; maintained coverage proves generic crit doubling and typed creature bonuses separately.",
    ),
    **_records(
        EB16_SMITE,
        "test_smite_highest_slot_fires_first",
        "test_smite_one_per_attack",
        "test_smite_consumes_correct_slot",
        reason="Maintained attack integration asserts highest-slot selection, one radiant payload, and exact slot consumption.",
    ),
    **_records(
        EB16_SMITE_GATES,
        "test_smite_disable_highest_falls_through",
        "test_smite_disable_all_no_smite",
        "test_smite_no_fire_on_miss",
        "test_smite_no_fire_on_ranged",
        "test_smite_no_slots_no_fire",
        "test_smite_fallthrough_on_empty_slot",
        reason="Maintained gate coverage deterministically asserts handler fallthrough and every no-op path.",
    ),
}

DODGING_ATTACK_CASES = _records(
    CONDITION_DODGE,
    "test_attack_vs_dodging",
    "test_attack_without_dodging",
    reason="Maintained direct modifier coverage asserts incoming disadvantage while Dodging and cleanup to NONE.",
)

EXTRA_ATTACK_CASES = {
    **_records(
        EB16_EXTRA_ATTACK,
        "test_has_attacked_applied_after_attack",
        "test_extra_attack_requires_has_attacked",
        "test_extra_attack_consumes_resource",
        reason="Maintained coverage executes the base and extra actions and asserts grant marker, resource, and cost state.",
    ),
    **_records(
        EB16_EXTRA_COUNTS,
        "test_resource_recharges_at_turn_start",
        "test_full_combat_round_l5",
        "test_full_combat_round_l11",
        reason="Maintained coverage proves full level-five, eleven, and twenty attack batches after owner-turn recharge.",
    ),
    **_records(
        SURGE_INTERLEAVED,
        "test_has_attacked_duration",
        reason="Maintained real-action coverage starts a fresh attack batch after the marker lifecycle resets.",
    ),
}

FACTION_SYSTEM_CASES = {
    **_records(
        EB06_FACTIONS,
        "test_faction_assignment",
        "test_is_ally_is_enemy",
        "test_get_entities_by_faction",
        "test_backward_compatibility",
        reason="Maintained entity coverage asserts self, same, opposing, and None-faction relationships plus registry queries.",
    ),
    **_records(
        EB06_VISIBLE_FACTIONS,
        "test_get_visible_enemies_allies",
        "test_get_available_actions_target_filter",
        reason="Maintained coverage filters sensed entities and discovered targets for enemies, allies, and all.",
    ),
    **_records(
        EB18_FACTION_END,
        "test_encounter_end_faction",
        reason="Maintained encounter coverage ends after authoritative faction survival changes.",
    ),
    **_records(
        NEW_FACTION,
        "test_is_threatened_faction",
        "test_opportunity_attack_respects_faction",
        status=CoverageStatus.ACTIVE,
        reason="The restored regression proves ally/enemy threat and opportunity-attack gates through real movement.",
    ),
}

FIGHTER_COMBAT_SIMULATION_CASES = {
    **_records(
        EB16_FACTORY,
        "test_fighter_available_actions_level_1",
        "test_fighter_available_actions_level_5",
        reason="Maintained factory coverage asserts the exact level-gated feature/resource surface.",
    ),
    **_records(
        EB16_FIGHTER_RESOURCES,
        "test_second_wind_action",
        "test_action_surge_grants_extra_action",
        reason="Maintained coverage executes both resource actions and asserts their state changes.",
    ),
    **_records(
        EB16_EXTRA_ATTACK,
        "test_extra_attack_workflow",
        reason="Maintained coverage executes and consumes the complete base/extra attack workflow.",
    ),
    **_records(
        SURGE_INTERLEAVED,
        "test_full_combat_round",
        reason="Maintained real-action coverage proves the full level-five surged combat round.",
    ),
}

FIGHTER_FACTORY_CASES = {
    **_records(
        EB16_FACTORY,
        "test_level_1_fighter",
        "test_level_5_fighter",
        reason="Maintained factory coverage asserts level-gated conditions, resources, actions, and ability improvements.",
    ),
    **_records(
        EB16_CHAMPION_FACTORY,
        "test_level_10_champion",
        reason="Maintained level-ten Champion coverage asserts the second style, Indomitable, crit feature, AC, and resources.",
    ),
    **_records(
        NEW_LEVEL_TWENTY_FIGHTER,
        "test_level_20_champion",
        status=CoverageStatus.ACTIVE,
        reason="The restored level-twenty factory regression directly asserts proficiency, three extra attacks, Superior Critical replacement, and Survivor ownership.",
    ),
    **_records(
        NEW_FACTORY,
        "test_helper_functions",
        "test_validation_errors",
        status=CoverageStatus.ACTIVE,
        reason="The restored boundary grid covers every helper transition and the cross-field validation failures.",
    ),
}

FRENZY_MAINTENANCE_CASES = _records(
    NEW_FRENZY_SEQUENCE,
    "test_frenzy_maintenance",
    status=CoverageStatus.ACTIVE,
    reason="The restored real attack sequence proves both Frenzy conditions survive qualifying activity and cascade away after subsequent inactivity.",
)

GREAT_WEAPON_FIGHTING_CASES = {
    **_records(
        MODIFIED_ROLL,
        "test_create_modified_dice_roll",
        reason="Maintained value-object coverage also asserts immutability and every causal metadata field.",
    ),
    **_records(
        EB16_FIGHTING_STYLES,
        "test_great_weapon_fighting_condition",
        reason="Maintained factory coverage asserts handler registration, toggleability, and cleanup.",
    ),
    **_records(
        EB03_GWF,
        "test_great_weapon_fighting_attack",
        "test_gwf_does_not_apply_to_ranged",
        "test_gwf_does_not_apply_to_one_handed",
        reason="Maintained deterministic damage-event coverage proves eligible rerolls and both weapon gates.",
    ),
    **_records(
        EB03_GWF,
        "test_gwf_statistics",
        status=CoverageStatus.RETIRED,
        reason="The archived random print-only sampling loop had no stable assertion; deterministic face-by-face coverage replaces it.",
    ),
}

IMPROVED_CRITICAL_CASES = _records(
    EB16_CRITICAL,
    "test_get_natural_roll",
    "test_default_threshold",
    "test_improved_critical_threshold",
    "test_superior_critical_threshold",
    "test_advantage_with_improved_critical",
    "test_condition_application",
    "test_ranged_vs_melee_thresholds",
    reason="Maintained Champion coverage asserts natural-roll outcomes, both thresholds, both weapon families, replacement, and cleanup.",
)

INDOMITABLE_CASES = {
    **_records(
        EB16_INDOMITABLE,
        "test_indomitable_basic",
        "test_indomitable_triggers_on_failure",
        "test_indomitable_no_trigger_on_success",
        "test_indomitable_resource_consumed",
        "test_indomitable_long_rest_recharge",
        reason="Maintained deterministic save coverage asserts resource ownership, success/failure gates, reroll, spend, and recharge.",
    ),
    **_records(
        NEW_FACTORY,
        "test_indomitable_multiple_uses",
        status=CoverageStatus.ACTIVE,
        reason="The restored helper boundary grid asserts one, two, and three-use level transitions.",
    ),
}

LUCKY_FEAT_CASES = {
    **_records(
        EB16_LUCKY,
        "test_lucky_feature_application",
        "test_lucky_on_attack_roll",
        reason="Maintained deterministic processor coverage asserts resource creation, low-roll rewrite, metadata, and spend.",
    ),
    **_records(
        EB16_LUCKY_POLICY,
        "test_lucky_on_saving_throw",
        "test_lucky_on_skill_check",
        reason="The archived cases were random print-only loops; maintained coverage asserts typed SAVE and CHECK triggers and one processor policy.",
    ),
    **_records(
        EB16_LUCKY_POLICY,
        "test_lucky_does_not_trigger_on_good_rolls",
        reason="Maintained deterministic coverage asserts the exact good-roll no-op and unchanged resource.",
    ),
}

PVP_EXTRA_ATTACK_CASES = _records(
    EB16_EXTRA_ATTACK,
    "test_pvp_extra_attack",
    reason="The archived case asserted only initiative membership; maintained coverage proves the actual owner-turn resource workflow deterministically.",
)

RELENTLESS_INTIMIDATING_CASES = {
    **_records(
        EB16_RAGE_EVENTS,
        "test_relentless_rage_with_real_combat",
        reason="Maintained real-damage coverage asserts successful survival, failed death, resource use, and life state.",
    ),
    **_records(
        NEW_INTIMIDATING,
        "test_intimidating_presence_uses_saving_throw",
        "test_intimidating_presence_event_integration",
        "test_intimidating_presence_variable_results",
        "test_intimidating_presence_immunity",
        status=CoverageStatus.ACTIVE,
        reason="The restored deterministic regression covers failed/successful saves, action events, fear, extension, end checks, and source-scoped immunity.",
    ),
}

SECOND_WIND_CASES = _records(
    EB16_FIGHTER_RESOURCES,
    "test_second_wind",
    reason="Maintained coverage executes healing, bonus-action/resource spend, and short-rest recharge.",
)

SHOVE_CASES = {
    **_records(
        EB10_SHOVE,
        "test_basic_shove",
        status=CoverageStatus.STALE,
        reason="The archived weight constant omitted kg-to-lb conversion; maintained coverage asserts the current BG3 formula, contest, cost, and displacement.",
    ),
    **_records(
        EB10_SHOVE_WEIGHT,
        "test_weight_limit",
        reason="Maintained coverage asserts capacity and distance across Strength and target-weight boundaries.",
    ),
    **_records(
        EB10_SHOVE,
        "test_ally_auto_succeed",
        "test_passive_skill_calculation",
        reason="Maintained coverage asserts ally auto-success and the exact selected passive contest skill/value.",
    ),
    **_records(
        EB10_SHOVE_NO_OA,
        "test_no_opportunity_attack",
        reason="Maintained coverage asserts forced-movement events, unchanged HP, and unspent watcher reaction.",
    ),
    **_records(
        NEW_SHOVE_WALL,
        "test_blocked_by_wall",
        status=CoverageStatus.ACTIVE,
        reason="The restored deterministic regression asserts endpoint, actual distance, blocker identity, and combat-log payload.",
    ),
}

SURVIVOR_CASES = {
    **_records(
        EB16_SURVIVOR,
        "test_survivor_heals_at_half_hp",
        "test_survivor_no_heal_above_half",
        "test_survivor_no_heal_at_zero",
        "test_survivor_removal_stops_healing",
        reason="Maintained coverage asserts threshold, zero-HP gate, exact healing, event message, and handler cleanup.",
    ),
    **_records(
        NEW_SURVIVOR,
        "test_survivor_with_negative_con",
        "test_survivor_multiple_turns",
        status=CoverageStatus.ACTIVE,
        reason="The restored regression asserts the negative-CON formula and exact repeated owner-turn healing.",
    ),
}

CENTRAL_LEDGER_SPECS = (
    ("ACTION_SURGE_CASES", "examples/test_action_surge.py"),
    ("AVAILABLE_ACTION_CASES", "examples/test_available_actions.py"),
    (
        "BARBARIAN_FAST_MOVEMENT_CASES",
        "examples/test_barbarian_fast_movement.py",
    ),
    (
        "BARBARIAN_FIGHTER_COMBAT_CASES",
        "examples/test_barbarian_fighter_combat.py",
    ),
    ("BARBARIAN_FRENZY_CASES", "examples/test_barbarian_frenzy.py"),
    (
        "BARBARIAN_MINDLESS_RAGE_CASES",
        "examples/test_barbarian_mindless_rage.py",
    ),
    (
        "BARBARIAN_MINOR_FEATURE_CASES",
        "examples/test_barbarian_minor_features.py",
    ),
    (
        "BARBARIAN_PERSISTENT_RAGE_CASES",
        "examples/test_barbarian_persistent_rage.py",
    ),
    ("BARBARIAN_RAGE_CASES", "examples/test_barbarian_rage.py"),
    (
        "BARBARIAN_RETALIATION_CASES",
        "examples/test_barbarian_retaliation.py",
    ),
    (
        "BARBARIAN_SRD_FEATURE_CASES",
        "examples/test_barbarian_srd_features.py",
    ),
    ("BRUTAL_CRITICAL_CASES", "examples/test_brutal_critical.py"),
    ("DIVINE_SMITE_CASES", "examples/test_divine_smite.py"),
    ("DODGING_ATTACK_CASES", "examples/test_dodging_attack.py"),
    ("EXTRA_ATTACK_CASES", "examples/test_extra_attack.py"),
    ("FACTION_SYSTEM_CASES", "examples/test_faction_system.py"),
    (
        "FIGHTER_COMBAT_SIMULATION_CASES",
        "examples/test_fighter_combat_simulation.py",
    ),
    ("FIGHTER_FACTORY_CASES", "examples/test_fighter_factory.py"),
    ("FRENZY_MAINTENANCE_CASES", "examples/test_frenzy_maintenance.py"),
    (
        "GREAT_WEAPON_FIGHTING_CASES",
        "examples/test_great_weapon_fighting.py",
    ),
    ("IMPROVED_CRITICAL_CASES", "examples/test_improved_critical.py"),
    ("INDOMITABLE_CASES", "examples/test_indomitable.py"),
    ("LUCKY_FEAT_CASES", "examples/test_lucky_feat.py"),
    ("PVP_EXTRA_ATTACK_CASES", "examples/test_pvp_extra_attack.py"),
    (
        "RELENTLESS_INTIMIDATING_CASES",
        "examples/test_relentless_rage_intimidating.py",
    ),
    ("SECOND_WIND_CASES", "examples/test_second_wind.py"),
    ("SHOVE_CASES", "examples/test_shove.py"),
    ("SURVIVOR_CASES", "examples/test_survivor.py"),
)


def _archived_test_names(old_path: str) -> set[str]:
    """Read authoritative named cases from one archived module."""
    root = Path(__file__).resolve().parents[2]
    tree = ast.parse((root / "to_archive" / old_path).read_text())
    return {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name.startswith("test_")
    }


def _condition_names(entity: Entity) -> set[str]:
    """Return compact condition identities for readable assertion failures."""
    return set(entity.active_conditions)


def _selector_exists(selector: str) -> bool:
    """Return whether a maintained selector resolves to a named test function."""
    test_path, test_name = selector.split("::", maxsplit=1)
    root = Path(__file__).resolve().parents[2]
    tree = ast.parse((root / test_path).read_text())
    return any(
        isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == test_name
        for node in ast.walk(tree)
    )


def test_class_action_legacy_manifest_accounts_for_all_188_cases() -> None:
    """Every assigned archived selector has one reviewed, live disposition."""
    namespace = globals()
    central_count = 0

    for variable, old_path in CENTRAL_LEDGER_SPECS:
        records = namespace[variable]
        assert isinstance(records, dict)
        assert set(records) == _archived_test_names(old_path)
        assert all(
            isinstance(record, CoverageRecord)
            and record.selector.startswith("tests/")
            and "::test_" in record.selector
            and _selector_exists(record.selector)
            and record.reason
            for record in records.values()
        )
        central_count += len(records)

    assert central_count == 181
    assert set(BARBARIAN_UNARMORED_ALREADY_MAPPED) == _archived_test_names(
        "examples/test_barbarian_unarmored_defense.py"
    )
    assert central_count + len(BARBARIAN_UNARMORED_ALREADY_MAPPED) == 188


def test_action_surge_enforces_one_use_per_turn_and_two_use_recharge() -> None:
    """A two-use feature still permits only one surge in the same turn."""
    reset_combat_state()
    get_map().create_rectangle(0, 0, 8, 8)
    fighter = create_skeleton(name="Two-Surge Fighter", position=(1, 1))
    fighter.add_condition(
        ActionSurgeFeature(
            source_entity_uuid=fighter.uuid,
            target_entity_uuid=fighter.uuid,
            num_uses=2,
        )
    )
    fighter.on_turn_start()
    resource = fighter.action_economy.resources["action_surge"]

    first = ActionSurge(source_entity_uuid=fighter.uuid, template=False).apply()

    assert first is not None and not first.canceled
    assert fighter.action_economy.actions.normalized_score == 2
    assert resource.current == 1
    assert "ActionSurging" in _condition_names(fighter)

    same_turn = ActionSurge(source_entity_uuid=fighter.uuid, template=False).apply()

    assert same_turn is not None and same_turn.canceled
    assert same_turn.status_message == "Already used Action Surge this turn"
    assert resource.current == 1

    fighter.on_turn_start()
    assert "ActionSurging" not in _condition_names(fighter)

    second = ActionSurge(source_entity_uuid=fighter.uuid, template=False).apply()

    assert second is not None and not second.canceled
    assert resource.current == 0

    fighter.action_economy.on_short_rest()
    assert resource.current == resource.maximum == 2


def test_standard_action_duration_and_blocking_rules_remain_distinct() -> None:
    """Dodge is owner-turn scoped; incapacitation and grappling deny different costs."""
    reset_combat_state()
    get_map().create_rectangle(0, 0, 10, 10)
    actor = create_skeleton(name="Action Actor", position=(1, 1), faction="heroes")
    other = create_skeleton(name="Other Actor", position=(2, 1), faction="monsters")

    dodge = Dodge(source_entity_uuid=actor.uuid, template=False).apply()

    assert dodge is not None and not dodge.canceled
    assert "Dodging" in _condition_names(actor)

    other.on_turn_start()
    assert "Dodging" in _condition_names(actor)

    actor.on_turn_start()
    assert "Dodging" not in _condition_names(actor)

    actor.add_condition(
        Incapacitated(source_entity_uuid=other.uuid, target_entity_uuid=actor.uuid)
    )
    incapacitated_actions = get_available_actions(actor)

    assert incapacitated_actions.position_actions
    assert not any(action.can_afford for action in incapacitated_actions.self_actions)

    actor.remove_condition("Incapacitated")
    actor.add_condition(
        Grappled(source_entity_uuid=other.uuid, target_entity_uuid=actor.uuid)
    )
    grappled_actions = get_available_actions(actor)

    assert grappled_actions.position_actions == []
    assert any(action.can_afford for action in grappled_actions.self_actions)


def test_fast_movement_tracks_armor_transitions_dash_and_feral_cleanup() -> None:
    """Fast Movement applies through medium armor and reacts to every transition."""
    reset_class_feature_state()
    barbarian = create_barbarian(
        BarbarianConfig(
            level=9,
            name="Mobile Barbarian",
            position=(1, 1),
            faction="heroes",
            primal_path=PrimalPathChoice.BERSERKER,
            asi_4=[("strength", 2)],
            asi_8=[("constitution", 2)],
        )
    )

    assert barbarian.action_economy.movement.normalized_score == 40
    assert barbarian.initiative.advantage is AdvantageStatus.ADVANTAGE

    light_armor = create_leather_armor(barbarian.uuid)
    assert barbarian.equipment.equip(light_armor, BodyPart.BODY)
    assert barbarian.equipment.body_armor is light_armor
    assert barbarian.action_economy.movement.normalized_score == 40

    medium_armor = create_chain_shirt(barbarian.uuid)
    assert barbarian.equipment.equip(medium_armor, BodyPart.BODY)
    assert barbarian.equipment.body_armor is medium_armor
    assert barbarian.action_economy.movement.normalized_score == 40

    heavy_armor = create_chain_mail(barbarian.uuid)
    assert barbarian.equipment.equip(heavy_armor, BodyPart.BODY)
    assert barbarian.equipment.body_armor is heavy_armor
    assert barbarian.action_economy.movement.normalized_score == 30

    assert barbarian.equipment.unequip(BodyPart.BODY) is heavy_armor
    assert barbarian.action_economy.movement.normalized_score == 40

    barbarian.add_condition(
        Dashing(
            source_entity_uuid=barbarian.uuid,
            target_entity_uuid=barbarian.uuid,
        )
    )
    assert barbarian.action_economy.movement.normalized_score == 80

    barbarian.remove_condition("Feral Instinct")
    assert barbarian.initiative.advantage is AdvantageStatus.NONE


def test_rage_resistance_maintenance_voluntary_end_and_heavy_armor_gate() -> None:
    """Rage keeps exact damage, marker, cleanup, and armor semantics."""
    reset_class_feature_state()
    barbarian = create_barbarian(
        BarbarianConfig(
            level=5,
            name="Rage Barbarian",
            position=(1, 1),
            faction="heroes",
            asi_4=[("strength", 2)],
        )
    )
    target = create_book_target(position=(2, 1))
    Entity.update_all_entities_senses(max_distance=20)

    available_before = get_available_actions(barbarian)
    rage_rows = [
        action
        for action in available_before.self_actions
        if action.template_name == "Rage"
    ]
    assert len(rage_rows) == 1
    rage_row = rage_rows[0]
    assert len(rage_row.valid_targets) == 1
    assert rage_row.valid_targets[0].target_uuid is None

    base_damages = barbarian.get_damages(
        WeaponSlot.MELEE_MAIN,
        target.uuid,
    )
    assert base_damages and base_damages[0].damage_bonus is not None
    base_melee_damage_bonus = (
        base_damages[0].damage_bonus.normalized_score
    )
    rage_resource = barbarian.action_economy.resources["rage"]
    rage_uses_before = rage_resource.current
    bonus_actions_before = (
        barbarian.action_economy.bonus_actions.normalized_score
    )

    rage = execute_action(
        barbarian,
        rage_row.template_name,
        rage_row.valid_targets[0],
    )

    assert rage is not None and not rage.canceled
    assert rage_resource.current == rage_uses_before - 1
    assert (
        barbarian.action_economy.bonus_actions.normalized_score
        == bonus_actions_before - 1
    )
    strength_save = barbarian.saving_throws.get_saving_throw("strength")
    assert strength_save.bonus.advantage is AdvantageStatus.ADVANTAGE
    raging_damages = barbarian.get_damages(
        WeaponSlot.MELEE_MAIN,
        target.uuid,
    )
    assert raging_damages and raging_damages[0].damage_bonus is not None
    assert (
        raging_damages[0].damage_bonus.normalized_score
        == base_melee_damage_bonus + 2
    )
    assert barbarian.equipment.melee_damage_bonus.normalized_score == 2
    assert barbarian.health.get_resistance(DamageType.BLUDGEONING) is ResistanceStatus.RESISTANCE
    assert barbarian.health.get_resistance(DamageType.PIERCING) is ResistanceStatus.RESISTANCE
    assert barbarian.health.get_resistance(DamageType.SLASHING) is ResistanceStatus.RESISTANCE
    assert barbarian.health.get_resistance(DamageType.FIRE) is ResistanceStatus.NONE
    assert deal_damage_to(
        barbarian,
        10,
        DamageType.SLASHING,
        source_uuid=target.uuid,
    ) == 5
    assert deal_damage_to(
        barbarian,
        10,
        DamageType.FIRE,
        source_uuid=target.uuid,
    ) == 10
    assert "HasTakenDamage" in _condition_names(barbarian)

    barbarian.on_turn_start()
    assert "Raging" in _condition_names(barbarian)
    assert "HasTakenDamage" not in _condition_names(barbarian)

    barbarian.on_turn_start()
    assert "Raging" not in _condition_names(barbarian)
    assert strength_save.bonus.advantage is AdvantageStatus.NONE
    assert barbarian.equipment.melee_damage_bonus.normalized_score == 0

    barbarian.action_economy.reset_all_costs()
    Rage(
        source_entity_uuid=barbarian.uuid,
        rage_damage=2,
        template=False,
    ).apply()
    barbarian.action_economy.reset_all_costs()
    force_attack_miss(barbarian)
    attack = Attack(
        source_entity_uuid=barbarian.uuid,
        target_entity_uuid=target.uuid,
        weapon_slot=WeaponSlot.MELEE_MAIN,
        template=False,
    ).apply()

    assert attack is not None and not attack.canceled
    assert "HasAttacked" in _condition_names(barbarian)
    barbarian.on_turn_start()
    assert "Raging" in _condition_names(barbarian)

    barbarian.action_economy.reset_all_costs()
    end_rage = EndRage(
        source_entity_uuid=barbarian.uuid,
        template=False,
    ).apply()

    assert end_rage is not None and not end_rage.canceled
    assert "Raging" not in _condition_names(barbarian)

    barbarian.action_economy.reset_all_costs()
    active_before_armor = Rage(
        source_entity_uuid=barbarian.uuid,
        rage_damage=2,
        template=False,
    ).apply()

    assert active_before_armor is not None and not active_before_armor.canceled
    assert "Raging" in _condition_names(barbarian)

    heavy_armor = create_chain_mail(barbarian.uuid)
    assert barbarian.equipment.equip(heavy_armor, BodyPart.BODY)
    assert "Raging" not in _condition_names(barbarian)

    barbarian.action_economy.reset_all_costs()
    barbarian.action_economy.resources["rage"].recharge()
    blocked = Rage(
        source_entity_uuid=barbarian.uuid,
        rage_damage=2,
        template=False,
    ).apply()

    assert blocked is not None and blocked.canceled
    assert blocked.status_message == "Cannot rage in heavy armor"


def test_frenzy_attack_turn_sequence_preserves_parent_child_and_costs() -> None:
    """A real attack maintains the complete Frenzy tree into the next turn."""
    reset_class_feature_state()
    barbarian = create_barbarian(
        BarbarianConfig(
            level=3,
            name="Sequenced Frenzy Barbarian",
            position=(1, 1),
            faction="heroes",
            primal_path=PrimalPathChoice.BERSERKER,
        )
    )
    target = create_book_target(name="Frenzy Target", position=(2, 1))
    Entity.update_all_entities_senses(max_distance=20)

    discovered = get_available_actions(barbarian)
    frenzy_rows = [
        action
        for action in discovered.self_actions
        if action.template_name == "Frenzy"
    ]
    assert len(frenzy_rows) == 1
    frenzy_row = frenzy_rows[0]
    assert len(frenzy_row.valid_targets) == 1
    assert frenzy_row.valid_targets[0].target_uuid is None
    rage_resource = barbarian.action_economy.resources["rage"]
    rage_before = rage_resource.current
    bonus_before = barbarian.action_economy.bonus_actions.normalized_score

    frenzy_event = execute_action(
        barbarian,
        frenzy_row.template_name,
        frenzy_row.valid_targets[0],
    )

    assert frenzy_event is not None and not frenzy_event.canceled
    assert rage_resource.current == rage_before - 1
    assert (
        barbarian.action_economy.bonus_actions.normalized_score
        == bonus_before - 1
    )
    assert {"Raging", "Frenzied"} <= _condition_names(barbarian)
    raging = barbarian.active_conditions["Raging"]
    frenzied = barbarian.active_conditions["Frenzied"]
    assert frenzied.parent_condition == raging.uuid
    assert frenzied.uuid in raging.sub_conditions
    assert isinstance(
        barbarian.get_action_template("Frenzied Strike"),
        FrenziedStrike,
    )

    force_attack_miss(barbarian)
    base_attack = Attack(
        source_entity_uuid=barbarian.uuid,
        target_entity_uuid=target.uuid,
        weapon_slot=WeaponSlot.MELEE_MAIN,
        template=False,
    ).apply()

    assert base_attack is not None and not base_attack.canceled
    assert "HasAttacked" in _condition_names(barbarian)

    barbarian.on_turn_start()

    assert {"Raging", "Frenzied"} <= _condition_names(barbarian)
    assert "HasAttacked" not in _condition_names(barbarian)
    assert barbarian.action_economy.bonus_actions.normalized_score == 1

    strike_rows = [
        action
        for action in get_available_actions(barbarian).entity_actions
        if action.template_name == "Frenzied Strike"
    ]
    assert strike_rows
    strike_row = next(
        action
        for action in strike_rows
        if any(
            candidate.target_uuid == target.uuid
            for candidate in action.valid_targets
        )
    )
    strike_target = next(
        candidate
        for candidate in strike_row.valid_targets
        if candidate.target_uuid == target.uuid
    )
    strike_bonus_before = (
        barbarian.action_economy.bonus_actions.normalized_score
    )
    force_attack_miss(barbarian)

    strike_event = execute_action(
        barbarian,
        strike_row.template_name,
        strike_target,
    )

    assert strike_event is not None and not strike_event.canceled
    assert isinstance(strike_event, AttackEvent)
    assert strike_event.attack_outcome is AttackOutcome.MISS
    assert strike_event.weapon_name == "Greataxe"
    assert strike_event.damage_types == [DamageType.SLASHING]
    assert (
        barbarian.action_economy.bonus_actions.normalized_score
        == strike_bonus_before - 1
    )
    assert {"Raging", "Frenzied", "HasAttacked"} <= _condition_names(
        barbarian
    )

    barbarian.on_turn_start()
    assert {"Raging", "Frenzied"} <= _condition_names(barbarian)
    assert "HasAttacked" not in _condition_names(barbarian)

    barbarian.on_turn_start()
    assert "Raging" not in _condition_names(barbarian)
    assert "Frenzied" not in _condition_names(barbarian)
    assert barbarian.get_action_template("Frenzied Strike") is None


def test_rage_death_and_frenzy_cleanup_do_not_leave_stale_state() -> None:
    """Death removes rage, while Frenzy owns and cleans its attack without exhaustion."""
    reset_class_feature_state()
    barbarian = create_barbarian(
        BarbarianConfig(
            level=3,
            name="Frenzy Barbarian",
            position=(1, 1),
            faction="heroes",
            primal_path=PrimalPathChoice.BERSERKER,
        )
    )
    damage_source = create_book_target(position=(2, 1))

    frenzy = Frenzy(
        source_entity_uuid=barbarian.uuid,
        rage_damage=2,
        template=False,
    ).apply()

    assert frenzy is not None and not frenzy.canceled
    assert "Raging" in _condition_names(barbarian)
    assert "Frenzied" in _condition_names(barbarian)
    assert barbarian.get_action_template("Frenzied Strike") is not None

    set_hp(barbarian, 1)
    deal_damage_to(
        barbarian,
        100,
        DamageType.FIRE,
        source_uuid=damage_source.uuid,
    )

    assert barbarian.health.life_state is LifeState.DEAD
    assert "Raging" not in _condition_names(barbarian)
    assert "Frenzied" not in _condition_names(barbarian)
    assert barbarian.get_action_template("Frenzied Strike") is None
    assert "Exhaustion" not in _condition_names(barbarian)
    assert "Exhausted" not in _condition_names(barbarian)

    reset_class_feature_state()
    armored = create_barbarian(
        BarbarianConfig(
            level=3,
            name="Armored Frenzy Barbarian",
            position=(1, 1),
            faction="heroes",
            primal_path=PrimalPathChoice.BERSERKER,
        )
    )
    assert armored.equipment.equip(create_chain_mail(armored.uuid), BodyPart.BODY)

    heavy_frenzy = Frenzy(
        source_entity_uuid=armored.uuid,
        rage_damage=2,
        template=False,
    ).apply()

    assert heavy_frenzy is not None and heavy_frenzy.canceled
    assert heavy_frenzy.status_message == "Cannot frenzy in heavy armor"


def test_intimidating_presence_save_extension_range_and_immunity() -> None:
    """Intimidating Presence preserves its save, extension, range, and immunity lifecycle."""
    reset_class_feature_state(width=30, height=8)
    barbarian = create_barbarian(
        BarbarianConfig(
            level=10,
            name="Intimidating Barbarian",
            position=(1, 1),
            faction="heroes",
            primal_path=PrimalPathChoice.BERSERKER,
            asi_4=[("strength", 2)],
            asi_8=[("constitution", 2)],
        )
    )
    frightened_target = create_book_target(name="Frightened Target", position=(3, 1))
    resistant_target = create_book_target(name="Resistant Target", position=(3, 2))
    Entity.update_all_entities_senses(max_distance=100)

    with patch("dnd.core.dice.random.randint", return_value=1):
        frightened_event = IntimidatingPresence(
            source_entity_uuid=barbarian.uuid,
            target_entity_uuid=frightened_target.uuid,
            template=False,
        ).apply()

    assert frightened_event is not None and not frightened_event.canceled
    frightened = frightened_target.active_conditions["Frightened"]
    assert frightened.source_entity_uuid == barbarian.uuid
    assert frightened.duration.duration == 1

    frightened.duration.duration = 0
    barbarian.action_economy.reset_all_costs()
    extended = ExtendIntimidatingPresence(
        source_entity_uuid=barbarian.uuid,
        target_entity_uuid=frightened_target.uuid,
        template=False,
    ).apply()

    assert extended is not None and not extended.canceled
    assert frightened.duration.duration == 1

    frightened_target.senses.position = (20, 1)
    frightened_target.update_entity_senses(max_distance=100)
    TurnEndEvent(
        source_entity_uuid=frightened_target.uuid,
        target_entity_uuid=frightened_target.uuid,
        encounter_uuid=uuid4(),
        entity_uuid=frightened_target.uuid,
        round_number=1,
        turn_index=0,
        phase=EventPhase.DECLARATION,
    ).phase_to(EventPhase.EXECUTION)

    assert "Frightened" not in _condition_names(frightened_target)

    barbarian.action_economy.reset_all_costs()
    with patch("dnd.core.dice.random.randint", return_value=20):
        resisted = IntimidatingPresence(
            source_entity_uuid=barbarian.uuid,
            target_entity_uuid=resistant_target.uuid,
            template=False,
        ).apply()

    assert resisted is not None and not resisted.canceled
    immunity = resistant_target.active_conditions["Intimidating Presence Immunity"]
    assert immunity.source_entity_uuid == barbarian.uuid

    barbarian.action_economy.reset_all_costs()
    immune_retry = IntimidatingPresence(
        source_entity_uuid=barbarian.uuid,
        target_entity_uuid=resistant_target.uuid,
        template=False,
    ).apply()

    assert immune_retry is not None and immune_retry.canceled
    assert immune_retry.status_message == "Target is immune (saved within 24h)"


def test_brutal_critical_channels_compose_and_clean_independently() -> None:
    """General crit dice affect all weapons while Brutal Critical remains melee-only."""
    reset_combat_state()
    get_map().create_rectangle(0, 0, 8, 8)
    barbarian = create_skeleton(name="Brutal Critical Actor", position=(1, 1))

    assert barbarian.get_crit_extra_dice(WeaponSlot.MELEE_MAIN) == 0
    assert barbarian.get_crit_extra_dice(WeaponSlot.RANGED_MAIN) == 0

    general_modifier = NumericalModifier.create(
        source_entity_uuid=barbarian.uuid,
        name="General Critical Die",
        value=1,
    )
    barbarian.equipment.crit_extra_dice.self_static.add_value_modifier(
        general_modifier
    )
    barbarian.add_condition(
        BrutalCritical(
            source_entity_uuid=barbarian.uuid,
            target_entity_uuid=barbarian.uuid,
            extra_dice=2,
        )
    )

    assert barbarian.get_crit_extra_dice(WeaponSlot.MELEE_MAIN) == 3
    assert barbarian.get_crit_extra_dice(WeaponSlot.RANGED_MAIN) == 1

    barbarian.remove_condition("Brutal Critical")

    assert barbarian.get_crit_extra_dice(WeaponSlot.MELEE_MAIN) == 1
    assert barbarian.get_crit_extra_dice(WeaponSlot.RANGED_MAIN) == 1


def test_level_twenty_fighter_factory_replaces_champion_features() -> None:
    """The level-twenty factory owns the complete final Champion surface."""
    reset_class_feature_state()
    fighter = create_fighter(
        FighterConfig(
            level=20,
            name="Restored Legendary Champion",
            position=(1, 1),
            faction="heroes",
            fighting_style="archery",
            second_fighting_style="defense",
            equipment_preset="archery",
            asi_4=[("strength", 2)],
            asi_6=[("constitution", 2)],
            asi_8=[("dexterity", 2)],
            asi_12=[("wisdom", 2)],
            asi_14=[("constitution", 2)],
            asi_16=[("intelligence", 2)],
            asi_19=[("charisma", 2)],
        )
    )

    condition_names = _condition_names(fighter)
    extra_attack = fighter.active_conditions["Extra Attack"]

    assert fighter.proficiency_bonus.normalized_score == 6
    assert isinstance(extra_attack, ExtraAttackFeature)
    assert extra_attack.extra_attacks == 3
    assert fighter.action_economy.resources["extra_attacks"].maximum == 3
    assert "Superior Critical" in condition_names
    assert "Improved Critical" not in condition_names
    assert fighter.get_crit_threshold(WeaponSlot.MELEE_MAIN) == 18
    assert fighter.get_crit_threshold(WeaponSlot.RANGED_MAIN) == 18
    assert "Survivor" in condition_names
    assert fighter.get_event_handler_by_name("Survivor") is not None


def test_fighter_factory_threshold_helpers_and_validation_grid() -> None:
    """Factory thresholds and cross-field constraints remain exact at boundaries."""
    assert [get_proficiency_bonus(level) for level in (1, 4, 5, 8, 9, 12, 13, 16, 17, 20)] == [
        2,
        2,
        3,
        3,
        4,
        4,
        5,
        5,
        6,
        6,
    ]
    assert [get_extra_attacks(level) for level in (4, 5, 10, 11, 19, 20)] == [
        0,
        1,
        1,
        2,
        2,
        3,
    ]
    assert [get_action_surge_uses(level) for level in (1, 2, 16, 17, 20)] == [
        0,
        1,
        1,
        2,
        2,
    ]
    assert [get_indomitable_uses(level) for level in (8, 9, 12, 13, 16, 17)] == [
        0,
        1,
        1,
        2,
        2,
        3,
    ]

    with pytest.raises(ValidationError):
        FighterConfig(level=1, bonus_plus_2="strength", bonus_plus_1="strength")
    with pytest.raises(ValidationError):
        FighterConfig(
            level=5,
            fighting_style="defense",
            second_fighting_style="archery",
            asi_4=[("strength", 2)],
        )
    with pytest.raises(ValidationError):
        FighterConfig(
            level=10,
            fighting_style="defense",
            second_fighting_style="defense",
            asi_4=[("strength", 2)],
            asi_6=[("constitution", 2)],
            asi_8=[("wisdom", 2)],
        )
    with pytest.raises(ValidationError):
        FighterConfig(level=5, fighting_style="defense")
    with pytest.raises(ValidationError):
        FighterConfig(level=5, fighting_style="defense", asi_4=[("strength", 1)])


def test_faction_relationships_gate_threat_and_opportunity_attacks() -> None:
    """Allies neither threaten nor opportunity-attack one another; enemies do."""
    for watcher_faction, expected_attacks in (("heroes", 0), ("monsters", 1)):
        reset_combat_state()
        get_map().create_rectangle(0, 0, 12, 12)
        watcher = create_skeleton(
            name="Watcher",
            position=(5, 5),
            faction=watcher_faction,
        )
        mover = create_skeleton(
            name="Mover",
            position=(5, 6),
            faction="heroes",
        )
        add_opportunity_attack_handler(watcher)
        Entity.update_all_entities_senses(max_distance=20)

        assert mover.is_threatened() is (watcher_faction == "monsters")

        force_attack_hit(watcher)
        hp_before = get_hp(mover)
        moved = Move(
            source_entity_uuid=mover.uuid,
            end_position=(5, 8),
            use_movement_cost=False,
            template=False,
        ).apply()
        opportunity_attacks = [
            event
            for event in EventQueue.get_events_by_type(EventType.ATTACK)
            if event.name == "Opportunity Attack"
            and event.phase is EventPhase.COMPLETION
        ]

        assert moved is not None and not moved.canceled
        assert len(opportunity_attacks) == expected_attacks
        if expected_attacks:
            assert get_hp(mover) < hp_before
        else:
            assert get_hp(mover) == hp_before


def test_shove_stops_before_wall_and_preserves_blocker_log() -> None:
    """A successful shove reports both authoritative endpoint and blocker."""
    reset_core_action_state()
    get_map().set_tile(5, 2, walkable=False, visible=False, name="Wall")
    shover = strong_entity(
        name="Wall Shover",
        position=(2, 2),
        faction="heroes",
        strength=18,
    )
    target = strong_entity(
        name="Wall Target",
        position=(3, 2),
        faction="monsters",
        strength=10,
        weight=100,
    )
    Entity.update_all_entities_senses(max_distance=20)

    with fixed_dice(20):
        event = Shove(
            source_entity_uuid=shover.uuid,
            target_entity_uuid=target.uuid,
            template=False,
        ).apply()

    assert isinstance(event, ShoveEvent)
    assert not event.canceled
    assert event.contest_success is True
    assert event.end_position == target.position == (4, 2)
    assert event.blocked_by == "Wall"
    assert event.combat_log is not None
    assert event.combat_log.data["blocked_by"] == "Wall"

    forced_logs = [
        entry
        for entry in event.combat_log.sub_entries
        if entry.data.get("type") == "forced_movement"
    ]
    assert len(forced_logs) == 1
    assert forced_logs[0].data["blocked_by"] == "Wall"
    assert forced_logs[0].data["actual_distance"] == 5
    assert "blocked by Wall" in forced_logs[0].compact


def _survivor_actor(*, constitution: int) -> Entity:
    """Create a deterministic direct Survivor fixture."""
    return Entity.create(
        source_entity_uuid=uuid4(),
        name=f"CON {constitution} Survivor",
        config=EntityConfig(
            ability_scores=AbilityScoresConfig(
                strength=AbilityConfig(ability_score=16),
                dexterity=AbilityConfig(ability_score=14),
                constitution=AbilityConfig(ability_score=constitution),
                intelligence=AbilityConfig(ability_score=10),
                wisdom=AbilityConfig(ability_score=12),
                charisma=AbilityConfig(ability_score=10),
            ),
            health=HealthConfig(
                hit_dices=[
                    HitDiceConfig(
                        hit_dice_value=10,
                        hit_dice_count=18,
                        mode="average",
                    )
                ]
            ),
            position=(1, 1),
        ),
    )


def test_survivor_negative_constitution_and_repeated_turns() -> None:
    """Survivor uses the actual CON modifier and repeats while at half HP."""
    reset_combat_state()
    get_map().create_rectangle(0, 0, 8, 8)
    weak = _survivor_actor(constitution=6)
    weak.add_condition(
        Survivor(source_entity_uuid=weak.uuid, target_entity_uuid=weak.uuid)
    )
    weak_max_hp = get_hp(weak)
    set_hp(weak, weak_max_hp // 2)
    weak_before = get_hp(weak)

    weak.on_turn_start()

    assert weak.ability_scores.constitution.modifier == -2
    assert get_hp(weak) == weak_before + 3

    steady = _survivor_actor(constitution=14)
    steady.add_condition(
        Survivor(source_entity_uuid=steady.uuid, target_entity_uuid=steady.uuid)
    )
    steady_max_hp = get_hp(steady)
    set_hp(steady, steady_max_hp // 3)
    hp_values = [get_hp(steady)]

    for _ in range(3):
        steady.on_turn_start()
        hp_values.append(get_hp(steady))

    assert [
        later - earlier
        for earlier, later in zip(hp_values, hp_values[1:])
    ] == [7, 7, 7]
