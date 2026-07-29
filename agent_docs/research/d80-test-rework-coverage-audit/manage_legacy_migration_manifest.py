"""Build and validate the reviewed migration manifest for all d80 legacy cases.

The lexical coverage map is an inventory, not evidence that a candidate is a
semantic replacement.  This tool therefore starts every old selector as
``unresolved`` and overlays only explicit mappings recorded in maintained
tests or exact mappings stated by the audit report.

Run:

    uv run python agent_docs/research/d80-test-rework-coverage-audit/\
manage_legacy_migration_manifest.py --build

Validation is also available without rewriting the checked-in manifest:

    uv run python agent_docs/research/d80-test-rework-coverage-audit/\
manage_legacy_migration_manifest.py
"""

from __future__ import annotations

import argparse
import ast
import csv
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
import re
import runpy
import sys
from typing import Any, Final, Iterable, Mapping


ROOT: Final = Path(__file__).resolve().parents[3]
AUDIT_DIR: Final = Path(__file__).resolve().parent
CASE_MAP_PATH: Final = AUDIT_DIR / "d80_case_coverage_map.tsv"
MANIFEST_PATH: Final = AUDIT_DIR / "d80_legacy_migration_manifest.tsv"
UNRESOLVED_PATH: Final = AUDIT_DIR / "d80_legacy_migration_unresolved.tsv"

MANIFEST_FIELDS: Final = (
    "old_selector",
    "disposition",
    "live_selector",
    "reason",
)
ALLOWED_DISPOSITIONS: Final = frozenset(
    {"active", "strengthened", "stale", "retired", "unresolved"}
)

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@dataclass(frozen=True)
class ManifestRow:
    """One reviewed legacy-case migration decision."""

    old_selector: str
    disposition: str
    live_selector: str
    reason: str


@dataclass(frozen=True)
class LedgerSpec:
    """One explicit mapping dictionary in a maintained regression module."""

    path: str
    variable: str
    old_path_hint: str | None = None
    default_disposition: str = "active"


@dataclass(frozen=True)
class OrdinalSpec:
    """A maintained module whose docstrings map numbered old cases."""

    old_path: str
    live_path: str
    batch: int | None = None


LEDGER_SPECS: Final = (
    LedgerSpec(
        "tests/manual/test_128_sorcerer_factory_legacy_contract.py",
        "LEGACY_ID_TO_ACTIVE_SELECTOR",
        "examples/test_sorcerer_factory.py",
    ),
    LedgerSpec(
        "tests/manual/test_131_advanced_item_world_legacy_contract.py",
        "LEGACY_CASE_TO_ACTIVE_SELECTOR",
        "examples/test_items_phase1_advanced.py",
    ),
    LedgerSpec(
        "tests/manual/test_131_inventory_use_actions_legacy_contract.py",
        "LEGACY_CASE_TO_ACTIVE_SELECTOR",
        "examples/test_inventory_use_actions.py",
    ),
    LedgerSpec(
        "tests/manual/test_133_item_core_lifecycle_legacy_contract.py",
        "PHASE1_CASES",
        "examples/test_items_phase1.py",
    ),
    LedgerSpec(
        "tests/manual/test_133_item_core_lifecycle_legacy_contract.py",
        "LIFECYCLE_CASES",
        "examples/test_items_lifecycle_hooks.py",
    ),
    LedgerSpec(
        "tests/manual/test_134_stackable_usable_item_legacy_contract.py",
        "STACKABLE_CASES",
        "examples/test_stackable_items.py",
    ),
    LedgerSpec(
        "tests/manual/test_134_stackable_usable_item_legacy_contract.py",
        "USABLE_CASES",
        "examples/test_usable_items.py",
    ),
    LedgerSpec(
        "tests/manual/test_135_stealth_lighting_legacy_contract.py",
        "STEALTH_CASES",
    ),
    LedgerSpec(
        "tests/manual/test_135_stealth_lighting_legacy_contract.py",
        "LIGHTING_CASES",
    ),
    LedgerSpec(
        "tests/manual/test_legacy_geometry_dice_coverage.py",
        "GEOMETRY_LEGACY_CASES",
        "examples/test_geometry.py",
    ),
    LedgerSpec(
        "tests/manual/test_legacy_geometry_dice_coverage.py",
        "DICE_PROCESSOR_LEGACY_CASES",
        "examples/test_dice_processors.py",
    ),
    LedgerSpec(
        "tests/manual/test_legacy_information_privacy_coverage.py",
        "INFORMATION_PRIVACY_LEDGER",
        "examples/test_info_leak_fixes.py",
    ),
    LedgerSpec(
        "tests/manual/test_legacy_reactive_reaction_coverage.py",
        "REACTIVE_SENSES_LEDGER",
        "examples/test_reactive_senses.py",
    ),
    LedgerSpec(
        "tests/manual/test_legacy_reactive_reaction_coverage.py",
        "INVISIBILITY_LEDGER",
        "examples/test_invisibility_oa_reveal.py",
    ),
    LedgerSpec(
        "tests/manual/test_legacy_reactive_reaction_coverage.py",
        "INTERCEPT_DODGE_LEDGER",
        "examples/test_intercept_dodge_roll.py",
    ),
    LedgerSpec(
        "tests/manual/test_138_skeleton_units_legacy_contract.py",
        "SKELETON_UNITS_LEGACY_CASES",
        "examples/test_skeleton_units.py",
    ),
    LedgerSpec(
        "tests/manual/test_141_combat_condition_legacy_contract.py",
        "COMBAT_CONDITION_LEGACY_CASES",
        "examples/combat_conditions.py",
    ),
    LedgerSpec(
        "tests/manual/test_142_item_equip_hooks_legacy_contract.py",
        "ITEM_EQUIP_HOOK_LEGACY_CASES",
        "examples/test_items_equip_hooks.py",
    ),
    LedgerSpec(
        "tests/manual/test_143_condition_removal_legacy_contract.py",
        "CONDITION_REMOVAL_LEGACY_CASES",
        "examples/test_condition_removal_system.py",
    ),
    LedgerSpec(
        "tests/manual/test_144_handler_toggle_legacy_contract.py",
        "HANDLER_TOGGLE_LEGACY_CASES",
        "examples/test_handler_toggle.py",
    ),
    LedgerSpec(
        "tests/manual/test_145_haste_legacy_manifest.py",
        "HASTE_SPELL_LEGACY_CASES",
        "examples/test_haste.py",
    ),
    LedgerSpec(
        "tests/manual/test_145_haste_legacy_manifest.py",
        "HASTE_POTION_LEGACY_CASES",
        "examples/test_haste_potion.py",
    ),
    LedgerSpec(
        "tests/manual/test_146_appearance_visual_legacy_contract.py",
        "APPEARANCE_API_LEGACY_CASES",
        "examples/test_appearance_api.py",
    ),
    LedgerSpec(
        "tests/manual/test_146_appearance_visual_legacy_contract.py",
        "EQUIPMENT_VISUAL_LEGACY_CASES",
        "examples/test_equipment_visual_metadata.py",
    ),
    LedgerSpec(
        "tests/manual/test_147_mapeditor_legacy_contract.py",
        "MAPEDITOR_LEGACY_CASES",
        "examples/test_mapeditor_api.py",
    ),
    LedgerSpec(
        "tests/manual/test_148_event_lifecycle_legacy_contract.py",
        "SAVING_THROW_EVENT_LEGACY_CASES",
        "examples/test_saving_throw_events.py",
    ),
    LedgerSpec(
        "tests/manual/test_148_event_lifecycle_legacy_contract.py",
        "TURN_END_HANDLER_LEGACY_CASES",
        "examples/test_turn_end_handler.py",
    ),
    LedgerSpec(
        "tests/manual/test_148_event_lifecycle_legacy_contract.py",
        "COMBAT_LOG_HIERARCHY_LEGACY_CASES",
        "examples/test_combat_log_hierarchy.py",
    ),
    LedgerSpec(
        "tests/manual/test_149_remaining_legacy_contract.py",
        "DIRECTIONAL_EVENT_STREAM_LEGACY_CASES",
        "examples/test_directional_event_stream.py",
    ),
    LedgerSpec(
        "tests/manual/test_149_remaining_legacy_contract.py",
        "PRONE_AUTO_STAND_LEGACY_CASES",
        "examples/test_prone_auto_stand.py",
    ),
    LedgerSpec(
        "tests/manual/test_149_remaining_legacy_contract.py",
        "LEGACY_SPATIAL_MIGRATION_CASES",
        "examples/test_legacy_migration.py",
    ),
    LedgerSpec(
        "tests/manual/test_142_class_action_legacy_contract.py",
        "ACTION_SURGE_CASES",
        "examples/test_action_surge.py",
    ),
    LedgerSpec(
        "tests/manual/test_142_class_action_legacy_contract.py",
        "AVAILABLE_ACTION_CASES",
        "examples/test_available_actions.py",
    ),
    LedgerSpec(
        "tests/manual/test_142_class_action_legacy_contract.py",
        "BARBARIAN_FAST_MOVEMENT_CASES",
        "examples/test_barbarian_fast_movement.py",
    ),
    LedgerSpec(
        "tests/manual/test_142_class_action_legacy_contract.py",
        "BARBARIAN_FIGHTER_COMBAT_CASES",
        "examples/test_barbarian_fighter_combat.py",
    ),
    LedgerSpec(
        "tests/manual/test_142_class_action_legacy_contract.py",
        "BARBARIAN_FRENZY_CASES",
        "examples/test_barbarian_frenzy.py",
    ),
    LedgerSpec(
        "tests/manual/test_142_class_action_legacy_contract.py",
        "BARBARIAN_MINDLESS_RAGE_CASES",
        "examples/test_barbarian_mindless_rage.py",
    ),
    LedgerSpec(
        "tests/manual/test_142_class_action_legacy_contract.py",
        "BARBARIAN_MINOR_FEATURE_CASES",
        "examples/test_barbarian_minor_features.py",
    ),
    LedgerSpec(
        "tests/manual/test_142_class_action_legacy_contract.py",
        "BARBARIAN_PERSISTENT_RAGE_CASES",
        "examples/test_barbarian_persistent_rage.py",
    ),
    LedgerSpec(
        "tests/manual/test_142_class_action_legacy_contract.py",
        "BARBARIAN_RAGE_CASES",
        "examples/test_barbarian_rage.py",
    ),
    LedgerSpec(
        "tests/manual/test_142_class_action_legacy_contract.py",
        "BARBARIAN_RETALIATION_CASES",
        "examples/test_barbarian_retaliation.py",
    ),
    LedgerSpec(
        "tests/manual/test_142_class_action_legacy_contract.py",
        "BARBARIAN_SRD_FEATURE_CASES",
        "examples/test_barbarian_srd_features.py",
    ),
    LedgerSpec(
        "tests/manual/test_142_class_action_legacy_contract.py",
        "BRUTAL_CRITICAL_CASES",
        "examples/test_brutal_critical.py",
    ),
    LedgerSpec(
        "tests/manual/test_142_class_action_legacy_contract.py",
        "DIVINE_SMITE_CASES",
        "examples/test_divine_smite.py",
    ),
    LedgerSpec(
        "tests/manual/test_142_class_action_legacy_contract.py",
        "DODGING_ATTACK_CASES",
        "examples/test_dodging_attack.py",
    ),
    LedgerSpec(
        "tests/manual/test_142_class_action_legacy_contract.py",
        "EXTRA_ATTACK_CASES",
        "examples/test_extra_attack.py",
    ),
    LedgerSpec(
        "tests/manual/test_142_class_action_legacy_contract.py",
        "FACTION_SYSTEM_CASES",
        "examples/test_faction_system.py",
    ),
    LedgerSpec(
        "tests/manual/test_142_class_action_legacy_contract.py",
        "FIGHTER_COMBAT_SIMULATION_CASES",
        "examples/test_fighter_combat_simulation.py",
    ),
    LedgerSpec(
        "tests/manual/test_142_class_action_legacy_contract.py",
        "FIGHTER_FACTORY_CASES",
        "examples/test_fighter_factory.py",
    ),
    LedgerSpec(
        "tests/manual/test_142_class_action_legacy_contract.py",
        "FRENZY_MAINTENANCE_CASES",
        "examples/test_frenzy_maintenance.py",
    ),
    LedgerSpec(
        "tests/manual/test_142_class_action_legacy_contract.py",
        "GREAT_WEAPON_FIGHTING_CASES",
        "examples/test_great_weapon_fighting.py",
    ),
    LedgerSpec(
        "tests/manual/test_142_class_action_legacy_contract.py",
        "IMPROVED_CRITICAL_CASES",
        "examples/test_improved_critical.py",
    ),
    LedgerSpec(
        "tests/manual/test_142_class_action_legacy_contract.py",
        "INDOMITABLE_CASES",
        "examples/test_indomitable.py",
    ),
    LedgerSpec(
        "tests/manual/test_142_class_action_legacy_contract.py",
        "LUCKY_FEAT_CASES",
        "examples/test_lucky_feat.py",
    ),
    LedgerSpec(
        "tests/manual/test_142_class_action_legacy_contract.py",
        "PVP_EXTRA_ATTACK_CASES",
        "examples/test_pvp_extra_attack.py",
    ),
    LedgerSpec(
        "tests/manual/test_142_class_action_legacy_contract.py",
        "RELENTLESS_INTIMIDATING_CASES",
        "examples/test_relentless_rage_intimidating.py",
    ),
    LedgerSpec(
        "tests/manual/test_142_class_action_legacy_contract.py",
        "SECOND_WIND_CASES",
        "examples/test_second_wind.py",
    ),
    LedgerSpec(
        "tests/manual/test_142_class_action_legacy_contract.py",
        "SHOVE_CASES",
        "examples/test_shove.py",
    ),
    LedgerSpec(
        "tests/manual/test_142_class_action_legacy_contract.py",
        "SURVIVOR_CASES",
        "examples/test_survivor.py",
    ),
    LedgerSpec(
        "tests/manual/test_legacy_ai_server_privacy_coverage.py",
        "LEGACY_CASES",
    ),
    LedgerSpec(
        "tests/manual/test_spell_legacy_migration_manifest.py",
        "SPELL_SPATIAL_LEGACY_CASES",
    ),
)


# These files are named as aggregate replacements by the audit report or by a
# maintained parity module, but do not yet carry an exact old-selector-to-live-
# selector table.  Their rows intentionally remain unresolved.
AGGREGATE_REPLACEMENTS: Final = {
    "examples/test_action_overrides.py": (
        "tests/manual/test_126_action_override_runtime.py"
    ),
    "examples/test_action_overrides_exec.py": (
        "tests/manual/test_126_action_override_runtime.py"
    ),
    "examples/test_tier1_spells.py": (
        "tests/manual/test_131_tier1_spell_legacy_gaps.py"
    ),
    "examples/test_shatter.py": "tests/manual/test_126_shatter.py",
    "examples/test_lightning_bolt.py": "tests/manual/test_127_lightning_bolt.py",
    "examples/test_barbarian_unarmored_defense.py": (
        "tests/manual/test_132_barbarian_unarmored_defense.py"
    ),
    "examples/test_antimagic_field.py": (
        "tests/manual/test_128_antimagic_field.py"
    ),
    "examples/test_disintegrate.py": "tests/manual/test_129_disintegrate.py",
    "examples/test_tier2_spells.py": "tests/manual/test_130_tier2_spells.py",
    "examples/test_new_spells_batch4.py": (
        "tests/manual/test_133_new_spells_batch4_legacy_contract.py"
    ),
    "examples/test_cleric_batch1.py": (
        "tests/manual/test_134_cleric_batch1_legacy_contract.py"
    ),
    "examples/test_cleric_batch2.py": (
        "tests/manual/test_135_cleric_batches_2_4_5_legacy_contract.py"
    ),
    "examples/test_cleric_batch4.py": (
        "tests/manual/test_135_cleric_batches_2_4_5_legacy_contract.py"
    ),
    "examples/test_cleric_batch5.py": (
        "tests/manual/test_135_cleric_batches_2_4_5_legacy_contract.py"
    ),
    "examples/test_healing_spells.py": (
        "tests/manual/test_136_healing_spell_legacy_contract.py"
    ),
    "examples/test_sense_buff_spells.py": (
        "tests/manual/test_137_sense_buff_spell_legacy_contract.py"
    ),
}

ORDINAL_SPECS: Final = (
    OrdinalSpec(
        "examples/test_healing_spells.py",
        "tests/manual/test_136_healing_spell_legacy_contract.py",
    ),
    OrdinalSpec(
        "examples/test_cleric_batch1.py",
        "tests/manual/test_134_cleric_batch1_legacy_contract.py",
    ),
    OrdinalSpec(
        "examples/test_tier2_spells.py",
        "tests/manual/test_130_tier2_spells.py",
    ),
    OrdinalSpec(
        "examples/test_new_spells_batch4.py",
        "tests/manual/test_133_new_spells_batch4_legacy_contract.py",
    ),
    OrdinalSpec(
        "examples/test_tier1_spells.py",
        "tests/manual/test_131_tier1_spell_legacy_gaps.py",
    ),
    OrdinalSpec(
        "examples/test_sense_buff_spells.py",
        "tests/manual/test_137_sense_buff_spell_legacy_contract.py",
    ),
    OrdinalSpec(
        "examples/test_antimagic_field.py",
        "tests/manual/test_128_antimagic_field.py",
    ),
    OrdinalSpec(
        "examples/test_cleric_batch2.py",
        "tests/manual/test_135_cleric_batches_2_4_5_legacy_contract.py",
        batch=2,
    ),
    OrdinalSpec(
        "examples/test_cleric_batch4.py",
        "tests/manual/test_135_cleric_batches_2_4_5_legacy_contract.py",
        batch=4,
    ),
    OrdinalSpec(
        "examples/test_lightning_bolt.py",
        "tests/manual/test_127_lightning_bolt.py",
    ),
    OrdinalSpec(
        "examples/test_cleric_batch5.py",
        "tests/manual/test_135_cleric_batches_2_4_5_legacy_contract.py",
        batch=5,
    ),
    OrdinalSpec(
        "examples/test_shatter.py",
        "tests/manual/test_126_shatter.py",
    ),
    OrdinalSpec(
        "examples/test_barbarian_unarmored_defense.py",
        "tests/manual/test_132_barbarian_unarmored_defense.py",
    ),
    OrdinalSpec(
        "examples/test_disintegrate.py",
        "tests/manual/test_129_disintegrate.py",
    ),
)

EB03_FILE: Final = "tests/engine/test_dice_event_semantics.py"
EB06_FILE: Final = "tests/engine/test_entity_composition.py"
EB15_FAMILIES_FILE: Final = (
    "tests/engine/test_spell_families.py"
)
MANUAL_95_FILE: Final = (
    "tests/manual/test_95_creature_presentation_contract.py"
)
TIER2_FILE: Final = "tests/manual/test_130_tier2_spells.py"

# Cases called out in module-level documentation as already covered elsewhere.
MANUAL_ORDINAL_MAPPINGS: Final = {
    ("examples/test_cleric_batch1.py", 4): (
        f"{EB15_FAMILIES_FILE}::"
        "test_eb_15_016_guidance_rewrites_one_skill_check_then_cleans_up"
    ),
    ("examples/test_cleric_batch1.py", 5): (
        f"{EB15_FAMILIES_FILE}::"
        "test_eb_15_016_guidance_rewrites_one_skill_check_then_cleans_up"
    ),
    ("examples/test_tier1_spells.py", 2): (
        f"{MANUAL_95_FILE}::"
        "test_preset_goblin_and_skeleton_keep_layered_presentation"
    ),
    ("examples/test_tier1_spells.py", 3): (
        f"{TIER2_FILE}::test_blight_rejects_construct"
    ),
    ("examples/test_tier1_spells.py", 5): (
        f"{EB15_FAMILIES_FILE}::"
        "test_eb_15_017_hold_person_failed_save_repeat_save_and_cleanup"
    ),
    ("examples/test_tier1_spells.py", 6): (
        f"{EB15_FAMILIES_FILE}::"
        "test_eb_15_017_hold_person_failed_save_repeat_save_and_cleanup"
    ),
    ("examples/test_tier1_spells.py", 7): (
        f"{EB15_FAMILIES_FILE}::"
        "test_eb_15_017_hold_person_failed_save_repeat_save_and_cleanup"
    ),
    ("examples/test_tier1_spells.py", 8): (
        f"{EB15_FAMILIES_FILE}::"
        "test_eb_15_018_hold_monster_excludes_undead_and_repeats_cleanup"
    ),
    ("examples/test_tier1_spells.py", 9): (
        f"{EB15_FAMILIES_FILE}::"
        "test_eb_15_018_hold_monster_excludes_undead_and_repeats_cleanup"
    ),
    ("examples/test_tier1_spells.py", 11): (
        f"{EB15_FAMILIES_FILE}::"
        "test_eb_15_018_hold_monster_excludes_undead_and_repeats_cleanup"
    ),
    ("examples/test_cleric_batch2.py", 1): (
        f"{EB15_FAMILIES_FILE}::"
        "test_eb_15_025_protective_abjurations_prevent_and_absorb_effects"
    ),
    ("examples/test_cleric_batch2.py", 2): (
        f"{EB15_FAMILIES_FILE}::"
        "test_eb_15_025_protective_abjurations_prevent_and_absorb_effects"
    ),
    ("examples/test_cleric_batch2.py", 3): (
        f"{EB15_FAMILIES_FILE}::"
        "test_eb_15_025_protective_abjurations_prevent_and_absorb_effects"
    ),
    ("examples/test_cleric_batch2.py", 4): (
        f"{EB15_FAMILIES_FILE}::"
        "test_eb_15_025_protective_abjurations_prevent_and_absorb_effects"
    ),
    ("examples/test_cleric_batch2.py", 5): (
        f"{EB15_FAMILIES_FILE}::"
        "test_eb_15_025_protective_abjurations_prevent_and_absorb_effects"
    ),
    ("examples/test_cleric_batch2.py", 6): (
        f"{EB15_FAMILIES_FILE}::"
        "test_eb_15_025_protective_abjurations_prevent_and_absorb_effects"
    ),
    ("examples/test_cleric_batch2.py", 8): (
        f"{EB15_FAMILIES_FILE}::"
        "test_eb_15_025_protective_abjurations_prevent_and_absorb_effects"
    ),
    ("examples/test_cleric_batch2.py", 11): (
        f"{EB15_FAMILIES_FILE}::"
        "test_eb_15_025_protective_abjurations_prevent_and_absorb_effects"
    ),
    ("examples/test_cleric_batch2.py", 12): (
        f"{EB15_FAMILIES_FILE}::"
        "test_eb_15_025_protective_abjurations_prevent_and_absorb_effects"
    ),
    ("examples/test_cleric_batch2.py", 13): (
        f"{EB15_FAMILIES_FILE}::"
        "test_eb_15_025_protective_abjurations_prevent_and_absorb_effects"
    ),
    ("examples/test_cleric_batch2.py", 14): (
        f"{EB06_FILE}::"
        "test_eb_06_013_saving_throw_and_skill_check_execute_event_phases"
    ),
    ("examples/test_cleric_batch4.py", 10): (
        f"{EB03_FILE}::"
        "test_eb_03_010_heal_roll_result_handlers_replace_final_roll"
    ),
    ("examples/test_cleric_batch5.py", 2): (
        f"{EB15_FAMILIES_FILE}::"
        "test_eb_15_023_restoration_spells_remove_supported_effects_only"
    ),
}


LEGACY_DOCSTRING_PATTERN: Final = re.compile(
    r"Legacy ``(?P<file>test_[A-Za-z0-9_]+\.py)::"
    r"(?P<case>test_[A-Za-z0-9_]+)``"
)

ORDINAL_PATTERN: Final = re.compile(
    r"(?:Old|Archived)\s+(?:case|cases|group|groups)\s+"
    r"(?P<ordinals>[^:;.]+)",
    flags=re.IGNORECASE,
)
BATCH_ORDINAL_PATTERN: Final = re.compile(
    r"Batch\s+(?P<batch>\d+)\s+old\s+(?:case|cases|group|groups)\s+"
    r"(?P<ordinals>[^:;.]+)",
    flags=re.IGNORECASE,
)
OVERRIDE_ID_PATTERN: Final = re.compile(
    r"^(?P<ids>(?:EX-)?[A-Z]\d+[a-z]?"
    r"(?:/(?:EX-)?[A-Z]\d+[a-z]?)*):"
)

EB07_FILE: Final = "tests/engine/test_condition_lifecycle.py"
EB14_FILE: Final = "tests/engine/test_spellcasting.py"
EB15_FILE: Final = "tests/engine/test_spell_families.py"

CHILD_PARENT_NOTIFICATION_MAPPINGS: Final = {
    1: f"{EB07_FILE}::test_eb_07_007_linked_conditions_clean_forward_and_notify_reverse",
    2: f"{EB07_FILE}::test_eb_07_007_linked_conditions_clean_forward_and_notify_reverse",
    3: f"{EB07_FILE}::test_eb_07_011_child_removal_policies_any_last_and_none",
    4: f"{EB07_FILE}::test_eb_07_011_child_removal_policies_any_last_and_none",
    5: f"{EB07_FILE}::test_eb_07_006_parent_removal_cascades_to_same_block_subconditions",
    6: f"{EB07_FILE}::test_eb_07_011_child_removal_policies_any_last_and_none",
    7: f"{EB07_FILE}::test_eb_07_011_child_removal_policies_any_last_and_none",
    8: f"{EB07_FILE}::test_eb_07_011_child_removal_policies_any_last_and_none",
    9: f"{EB07_FILE}::test_eb_07_011_child_removal_policies_any_last_and_none",
    10: f"{EB07_FILE}::test_eb_07_011_child_removal_policies_any_last_and_none",
    11: f"{EB07_FILE}::test_eb_07_011_child_removal_policies_any_last_and_none",
    12: f"{EB07_FILE}::test_eb_07_007_linked_conditions_clean_forward_and_notify_reverse",
    13: f"{EB07_FILE}::test_eb_07_007_linked_conditions_clean_forward_and_notify_reverse",
    14: f"{EB14_FILE}::test_eb_14_015_damage_and_death_break_concentration_deterministically",
    15: f"{EB14_FILE}::test_eb_14_010_concentration_links_cleanup_and_empty_casts",
    16: f"{EB14_FILE}::test_eb_14_010_concentration_links_cleanup_and_empty_casts",
    17: f"{EB15_FILE}::test_eb_15_006_zone_spells_create_spatial_handlers_and_cleanup_links",
    18: f"{EB15_FILE}::test_eb_15_006_zone_spells_create_spatial_handlers_and_cleanup_links",
    19: f"{EB07_FILE}::test_eb_07_007_linked_conditions_clean_forward_and_notify_reverse",
    20: f"{EB07_FILE}::test_eb_07_007_linked_conditions_clean_forward_and_notify_reverse",
    21: f"{EB15_FILE}::test_eb_15_017_hold_person_failed_save_repeat_save_and_cleanup",
    22: f"{EB15_FILE}::test_eb_15_017_hold_person_failed_save_repeat_save_and_cleanup",
    23: f"{EB15_FILE}::test_eb_15_018_hold_monster_excludes_undead_and_repeats_cleanup",
    24: f"{EB15_FILE}::test_eb_15_017_hold_person_failed_save_repeat_save_and_cleanup",
    25: f"{EB14_FILE}::test_eb_14_011_spell_registration_uses_templates_and_setup_order_matters",
    26: f"{EB14_FILE}::test_eb_14_010_concentration_links_cleanup_and_empty_casts",
    27: f"{EB14_FILE}::test_eb_14_014_drop_concentration_can_target_one_multi_slot_spell",
    28: f"{EB14_FILE}::test_eb_14_010_concentration_links_cleanup_and_empty_casts",
    29: f"{EB14_FILE}::test_eb_14_014_drop_concentration_can_target_one_multi_slot_spell",
    30: f"{EB07_FILE}::test_eb_07_007_linked_conditions_clean_forward_and_notify_reverse",
    31: f"{EB07_FILE}::test_eb_07_007_linked_conditions_clean_forward_and_notify_reverse",
    32: f"{EB07_FILE}::test_eb_07_011_child_removal_policies_any_last_and_none",
}


def read_case_map() -> dict[str, dict[str, str]]:
    """Read the authoritative old-case inventory and reject duplicates."""
    with CASE_MAP_PATH.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        rows: dict[str, dict[str, str]] = {}
        for raw in reader:
            selector = raw["old_selector"]
            if selector in rows:
                raise ValueError(f"duplicate selector in case map: {selector}")
            rows[selector] = dict(raw)
    if len(rows) != 1458:
        raise ValueError(
            f"expected 1,458 authoritative old selectors, found {len(rows)}"
        )
    return rows


def unresolved_reason(audit_row: Mapping[str, str]) -> str:
    """Explain why a lexical candidate is not yet a reviewed mapping."""
    status = audit_row["status"]
    candidate = audit_row["candidate_1"]
    score = audit_row["score_1"]
    if candidate:
        return (
            "No reviewed selector-level disposition. The static audit marked "
            f"this {status}; its top lexical candidate is {candidate} "
            f"(score {score}), which is not semantic evidence."
        )
    return (
        "No reviewed selector-level disposition and the static audit found no "
        "candidate. Manual behavior reconciliation is required."
    )


def resolve_case_key(
    key: str,
    old_rows: Mapping[str, Mapping[str, str]],
    old_path_hint: str | None,
) -> str:
    """Resolve one explicit ledger key to exactly one authoritative selector."""
    if key in old_rows:
        matches = [key]
    elif key.startswith("SF-"):
        token = key.lower().replace("-", "_")
        matches = [
            selector
            for selector in old_rows
            if selector.startswith("examples/test_sorcerer_factory.py::")
            and selector.split("::", 1)[1].startswith(f"test_{token}_")
        ]
    elif old_path_hint is not None:
        candidate = f"{old_path_hint}::{key}"
        matches = [candidate] if candidate in old_rows else []
    else:
        matches = [
            selector
            for selector in old_rows
            if selector.endswith(f"::{key}")
        ]
    if len(matches) != 1:
        raise ValueError(
            f"ledger key {key!r} resolved to {len(matches)} old selectors: "
            f"{matches}"
        )
    return matches[0]


def record_fields(
    value: Any,
    default_disposition: str,
) -> tuple[str, str, str]:
    """Normalize string and dataclass ledger values."""
    if isinstance(value, str):
        return value, default_disposition, ""
    selector = getattr(value, "selector", None)
    status = getattr(value, "status", default_disposition)
    reason = getattr(value, "reason", getattr(value, "rationale", ""))
    if not isinstance(selector, str):
        raise TypeError(f"unsupported ledger record: {value!r}")
    status_value = getattr(status, "value", status)
    if not isinstance(status_value, str) or status_value not in ALLOWED_DISPOSITIONS:
        raise ValueError(f"invalid ledger disposition: {status_value!r}")
    return selector, status_value, str(reason)


def apply_explicit_row(
    rows: dict[str, ManifestRow],
    explicit_sources: dict[str, str],
    row: ManifestRow,
    source: str,
) -> None:
    """Apply one reviewed row and reject duplicate or conflicting evidence."""
    previous_source = explicit_sources.get(row.old_selector)
    if previous_source is not None:
        previous = rows[row.old_selector]
        if previous != row:
            raise ValueError(
                f"conflicting mappings for {row.old_selector}: "
                f"{previous_source} versus {source}"
            )
        return
    rows[row.old_selector] = row
    explicit_sources[row.old_selector] = source


def overlay_code_ledgers(
    rows: dict[str, ManifestRow],
    old_rows: Mapping[str, Mapping[str, str]],
    explicit_sources: dict[str, str],
) -> None:
    """Load each explicit maintained mapping dictionary."""
    namespaces: dict[str, dict[str, Any]] = {}
    for spec in LEDGER_SPECS:
        namespace = namespaces.get(spec.path)
        if namespace is None:
            namespace = runpy.run_path(str(ROOT / spec.path))
            namespaces[spec.path] = namespace
        mapping = namespace.get(spec.variable)
        if isinstance(mapping, (tuple, list)):
            for value in mapping:
                old_selector = getattr(value, "old_selector", None)
                replacements = getattr(value, "replacements", None)
                disposition = getattr(value, "disposition", spec.default_disposition)
                reason = getattr(value, "rationale", getattr(value, "reason", ""))
                if not isinstance(old_selector, str):
                    raise TypeError(
                        f"{spec.path}:{spec.variable} row has no old_selector"
                    )
                if old_selector not in old_rows:
                    if old_selector.startswith("to_archive/"):
                        continue
                    raise ValueError(
                        f"{spec.path}:{spec.variable} names unknown selector "
                        f"{old_selector}"
                    )
                if (
                    not isinstance(replacements, tuple)
                    or len(replacements) != 1
                    or not isinstance(replacements[0], str)
                ):
                    raise TypeError(
                        f"{spec.path}:{spec.variable} row must have exactly "
                        "one replacement selector"
                    )
                disposition_value = getattr(disposition, "value", disposition)
                if disposition_value not in ALLOWED_DISPOSITIONS:
                    raise ValueError(
                        f"invalid ledger disposition: {disposition_value!r}"
                    )
                apply_explicit_row(
                    rows,
                    explicit_sources,
                    ManifestRow(
                        old_selector=old_selector,
                        disposition=str(disposition_value),
                        live_selector=replacements[0],
                        reason=str(reason),
                    ),
                    f"{spec.path}:{spec.variable}",
                )
            continue
        if not isinstance(mapping, dict):
            raise TypeError(
                f"{spec.path}:{spec.variable} is not a dictionary or row tuple"
            )
        for key, value in mapping.items():
            if not isinstance(key, str):
                raise TypeError(f"non-string ledger key in {spec.path}")
            old_selector = resolve_case_key(
                key,
                old_rows,
                spec.old_path_hint,
            )
            live_selector, disposition, authored_reason = record_fields(
                value,
                spec.default_disposition,
            )
            reason = authored_reason or (
                f"Explicitly mapped by {spec.path}:{spec.variable}."
            )
            apply_explicit_row(
                rows,
                explicit_sources,
                ManifestRow(
                    old_selector=old_selector,
                    disposition=disposition,
                    live_selector=live_selector,
                    reason=reason,
                ),
                f"{spec.path}:{spec.variable}",
            )


def iter_test_functions(tree: ast.AST) -> Iterable[ast.FunctionDef | ast.AsyncFunctionDef]:
    """Yield every named test function from one parsed module."""
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name.startswith("test_"):
                yield node


def overlay_docstring_mappings(
    rows: dict[str, ManifestRow],
    old_rows: Mapping[str, Mapping[str, str]],
    explicit_sources: dict[str, str],
) -> None:
    """Load one-to-one legacy selectors declared in maintained docstrings."""
    for path in sorted((ROOT / "tests").rglob("test_*.py")):
        relative = path.relative_to(ROOT).as_posix()
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=relative)
        for function in iter_test_functions(tree):
            docstring = ast.get_docstring(function) or ""
            for match in LEGACY_DOCSTRING_PATTERN.finditer(docstring):
                old_selector = (
                    f"examples/{match.group('file')}::{match.group('case')}"
                )
                if old_selector not in old_rows:
                    prefix_matches = [
                        selector
                        for selector in old_rows
                        if selector.startswith(f"{old_selector}_")
                    ]
                    if len(prefix_matches) != 1:
                        raise ValueError(
                            f"{relative}::{function.name} names unknown old "
                            f"selector {old_selector}; prefix matches were "
                            f"{prefix_matches}"
                        )
                    old_selector = prefix_matches[0]
                apply_explicit_row(
                    rows,
                    explicit_sources,
                    ManifestRow(
                        old_selector=old_selector,
                        disposition="active",
                        live_selector=f"{relative}::{function.name}",
                        reason=(
                            "The maintained test docstring declares this exact "
                            "one-to-one legacy replacement."
                        ),
                    ),
                    f"{relative}::{function.name}",
                )


def parse_ordinals(raw: str) -> set[int]:
    """Parse comma-separated integers and inclusive ranges from a docstring."""
    ordinals: set[int] = set()
    for token in re.findall(r"\d+(?:-\d+)?", raw):
        if "-" not in token:
            ordinals.add(int(token))
            continue
        start_raw, end_raw = token.split("-", 1)
        start = int(start_raw)
        end = int(end_raw)
        if end < start:
            raise ValueError(f"descending ordinal range: {token}")
        ordinals.update(range(start, end + 1))
    if not ordinals:
        raise ValueError(f"no ordinals found in {raw!r}")
    return ordinals


def old_selectors_for_path(
    old_path: str,
    old_rows: Mapping[str, Mapping[str, str]],
) -> list[str]:
    """Return one old file's selectors in authoritative source order."""
    return [
        selector
        for selector in old_rows
        if selector.startswith(f"{old_path}::")
    ]


def overlay_ordinal_replacement_modules(
    rows: dict[str, ManifestRow],
    old_rows: Mapping[str, Mapping[str, str]],
    explicit_sources: dict[str, str],
) -> None:
    """Read explicit old-case ordinal declarations from replacement modules."""
    for spec in ORDINAL_SPECS:
        old_selectors = old_selectors_for_path(spec.old_path, old_rows)
        path = ROOT / spec.live_path
        tree = ast.parse(
            path.read_text(encoding="utf-8"),
            filename=spec.live_path,
        )
        mapped: dict[int, list[str]] = defaultdict(list)
        for function in iter_test_functions(tree):
            docstring = ast.get_docstring(function) or ""
            if spec.batch is None:
                match = ORDINAL_PATTERN.search(docstring)
            else:
                match = next(
                    (
                        candidate
                        for candidate in BATCH_ORDINAL_PATTERN.finditer(docstring)
                        if int(candidate.group("batch")) == spec.batch
                    ),
                    None,
                )
            if match is None:
                continue
            live_selector = f"{spec.live_path}::{function.name}"
            for ordinal in parse_ordinals(match.group("ordinals")):
                mapped[ordinal].append(live_selector)

        for (old_path, ordinal), live_selector in MANUAL_ORDINAL_MAPPINGS.items():
            if old_path == spec.old_path:
                mapped[ordinal].append(live_selector)

        expected_ordinals = set(range(1, len(old_selectors) + 1))
        if set(mapped) != expected_ordinals:
            raise ValueError(
                f"{spec.old_path} ordinal mapping mismatch; missing "
                f"{sorted(expected_ordinals - set(mapped))}, extra "
                f"{sorted(set(mapped) - expected_ordinals)}"
            )
        for ordinal, old_selector in enumerate(old_selectors, start=1):
            live_selectors = list(dict.fromkeys(mapped[ordinal]))
            primary = live_selectors[0]
            companion_note = ""
            if len(live_selectors) > 1:
                companion_note = (
                    " Companion maintained selectors: "
                    + ", ".join(live_selectors[1:])
                    + "."
                )
            apply_explicit_row(
                rows,
                explicit_sources,
                ManifestRow(
                    old_selector=old_selector,
                    disposition="strengthened",
                    live_selector=primary,
                    reason=(
                        "The replacement module explicitly identifies this old "
                        "case/group ordinal and replays it with deterministic "
                        f"legal fixtures.{companion_note}"
                    ),
                ),
                f"{spec.live_path}:old case/group {ordinal}",
            )


def overlay_action_override_ids(
    rows: dict[str, ManifestRow],
    old_rows: Mapping[str, Mapping[str, str]],
    explicit_sources: dict[str, str],
) -> None:
    """Map every archived action-override ID declared by live docstrings."""
    live_path = "tests/manual/test_126_action_override_runtime.py"
    tree = ast.parse(
        (ROOT / live_path).read_text(encoding="utf-8"),
        filename=live_path,
    )
    live_by_id: dict[str, list[str]] = defaultdict(list)
    for function in iter_test_functions(tree):
        docstring = ast.get_docstring(function) or ""
        match = OVERRIDE_ID_PATTERN.match(docstring)
        if match is None:
            continue
        live_selector = f"{live_path}::{function.name}"
        for case_id in match.group("ids").split("/"):
            live_by_id[case_id].append(live_selector)

    old_by_id: dict[str, str] = {}
    for old_path in (
        "examples/test_action_overrides.py",
        "examples/test_action_overrides_exec.py",
    ):
        for old_selector in old_selectors_for_path(old_path, old_rows):
            match = re.search(r"::manual::(?P<id>[^:]+):", old_selector)
            if match is None:
                raise ValueError(f"missing override ID in {old_selector}")
            case_id = match.group("id")
            if case_id in old_by_id:
                raise ValueError(f"duplicate old override ID: {case_id}")
            old_by_id[case_id] = old_selector
    if set(live_by_id) != set(old_by_id):
        raise ValueError(
            "action-override ID mismatch; missing "
            f"{sorted(set(old_by_id) - set(live_by_id))}, extra "
            f"{sorted(set(live_by_id) - set(old_by_id))}"
        )

    for case_id, old_selector in old_by_id.items():
        live_selectors = list(dict.fromkeys(live_by_id[case_id]))
        primary = live_selectors[0]
        companion_note = ""
        if len(live_selectors) > 1:
            companion_note = (
                " Companion maintained selectors: "
                + ", ".join(live_selectors[1:])
                + "."
            )
        apply_explicit_row(
            rows,
            explicit_sources,
            ManifestRow(
                old_selector=old_selector,
                disposition="strengthened",
                live_selector=primary,
                reason=(
                    f"The maintained runtime matrix explicitly assigns legacy "
                    f"ID {case_id} to deterministic discovery/execution "
                    f"coverage.{companion_note}"
                ),
            ),
            f"{live_path}:legacy ID {case_id}",
        )


def overlay_audit_report(
    rows: dict[str, ManifestRow],
    explicit_sources: dict[str, str],
) -> None:
    """Apply exact report mappings and annotate aggregate-only claims."""
    child_parent_rows = [
        selector
        for selector in rows
        if selector.startswith("examples/test_child_parent_notification.py::")
    ]
    if len(child_parent_rows) != 32:
        raise ValueError(
            "expected 32 child-parent notification selectors, found "
            f"{len(child_parent_rows)}"
        )
    for case_number, live_selector in CHILD_PARENT_NOTIFICATION_MAPPINGS.items():
        prefix = (
            "examples/test_child_parent_notification.py::"
            f"test_{case_number}_"
        )
        matches = [
            selector for selector in child_parent_rows if selector.startswith(prefix)
        ]
        if len(matches) != 1:
            raise ValueError(
                f"child-parent case {case_number} resolved to {matches}"
            )
        apply_explicit_row(
            rows,
            explicit_sources,
            ManifestRow(
                old_selector=matches[0],
                disposition="strengthened",
                live_selector=live_selector,
                reason=(
                    "Manual reconciliation verified the archived custom-runner "
                    "case against the maintained condition/concentration "
                    "lifecycle contract; the isolated archived oracle is green."
                ),
            ),
            "root manual child-parent notification audit",
        )

    gust_old = (
        "examples/test_gust_of_wind.py::"
        "test_gust_terrain_reactive_paths"
    )
    gust_live = (
        "tests/engine/test_spell_families.py::"
        "test_eb_15_045_gust_terrain_removal_restores_cached_move_targets"
    )
    apply_explicit_row(
        rows,
        explicit_sources,
        ManifestRow(
            old_selector=gust_old,
            disposition="strengthened",
            live_selector=gust_live,
            reason=(
                "The audit reproduced and fixed the stale path-cache defect; "
                "both this exact old selector and the maintained regression pass."
            ),
        ),
        "D80 audit: Gust of Wind path restoration",
    )

    haste_partial = {
        "test_2_haste_extra_attack_suppression",
        "test_3_haste_action_surge",
        "test_7_haste_slow_action_surge",
        "test_10_haste_mid_turn_action_surge",
    }
    for case in haste_partial:
        old_selector = f"examples/test_haste.py::{case}"
        if rows[old_selector].disposition == "unresolved":
            rows[old_selector] = ManifestRow(
                old_selector=old_selector,
                disposition="unresolved",
                live_selector="",
                reason=(
                    "The audit identifies this as partial historical Haste "
                    "coverage and lists multiple strengthened replacements, but "
                    "does not record one exact selector-level mapping."
                ),
            )

    for old_path, replacement in AGGREGATE_REPLACEMENTS.items():
        for old_selector, row in tuple(rows.items()):
            if not old_selector.startswith(f"{old_path}::"):
                continue
            if row.disposition != "unresolved":
                continue
            rows[old_selector] = ManifestRow(
                old_selector=old_selector,
                disposition="unresolved",
                live_selector="",
                reason=(
                    f"The audit or maintained module names {replacement} as an "
                    "aggregate replacement, but no exact old-to-live selector "
                    "mapping is recorded for this case."
                ),
            )


def write_manifest(rows: Mapping[str, ManifestRow]) -> None:
    """Write the central manifest in authoritative old-selector order."""
    with MANIFEST_PATH.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=MANIFEST_FIELDS,
            delimiter="\t",
            lineterminator="\n",
        )
        writer.writeheader()
        for row in rows.values():
            writer.writerow(
                {
                    "old_selector": row.old_selector,
                    "disposition": row.disposition,
                    "live_selector": row.live_selector,
                    "reason": row.reason,
                }
            )


def write_unresolved_inventory(
    rows: Mapping[str, ManifestRow],
    audit_rows: Mapping[str, Mapping[str, str]],
) -> None:
    """Write a file-level unresolved queue suitable for parallel assignment."""
    grouped: dict[str, list[str]] = defaultdict(list)
    for old_selector, row in rows.items():
        if row.disposition == "unresolved":
            grouped[old_selector.split("::", 1)[0]].append(old_selector)
    fields = (
        "old_path",
        "unresolved_count",
        "strong_candidates",
        "partial_candidates",
        "weak_candidates",
        "unmapped_candidates",
        "aggregate_replacement_hint",
    )
    with UNRESOLVED_PATH.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=fields,
            delimiter="\t",
            lineterminator="\n",
        )
        writer.writeheader()
        for old_path in sorted(grouped, key=lambda item: (-len(grouped[item]), item)):
            selectors = grouped[old_path]
            statuses = Counter(audit_rows[item]["status"] for item in selectors)
            writer.writerow(
                {
                    "old_path": old_path,
                    "unresolved_count": len(selectors),
                    "strong_candidates": statuses["strong_semantic_candidate"],
                    "partial_candidates": statuses["partial_semantic_candidate"],
                    "weak_candidates": statuses["weak_semantic_candidate"],
                    "unmapped_candidates": statuses["unmapped_requires_review"],
                    "aggregate_replacement_hint": AGGREGATE_REPLACEMENTS.get(
                        old_path,
                        "",
                    ),
                }
            )


def build_manifest() -> None:
    """Build the manifest from the old inventory and reviewed evidence."""
    audit_rows = read_case_map()
    rows = {
        selector: ManifestRow(
            old_selector=selector,
            disposition="unresolved",
            live_selector="",
            reason=unresolved_reason(audit_row),
        )
        for selector, audit_row in audit_rows.items()
    }
    explicit_sources: dict[str, str] = {}
    overlay_code_ledgers(rows, audit_rows, explicit_sources)
    overlay_docstring_mappings(rows, audit_rows, explicit_sources)
    overlay_ordinal_replacement_modules(rows, audit_rows, explicit_sources)
    overlay_action_override_ids(rows, audit_rows, explicit_sources)
    overlay_audit_report(rows, explicit_sources)
    write_manifest(rows)
    write_unresolved_inventory(rows, audit_rows)


def read_manifest() -> list[ManifestRow]:
    """Read the checked-in manifest without collapsing duplicate rows."""
    with MANIFEST_PATH.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        if tuple(reader.fieldnames or ()) != MANIFEST_FIELDS:
            raise ValueError(
                f"manifest fields must be {MANIFEST_FIELDS}, got {reader.fieldnames}"
            )
        return [ManifestRow(**raw) for raw in reader]


def selector_exists(
    selector: str,
    cache: dict[str, ast.Module],
) -> bool:
    """Return whether a live Python selector names an existing AST node."""
    parts = selector.split("::")
    if len(parts) < 2:
        return False
    relative, *node_names = parts
    path = ROOT / relative
    if not path.is_file():
        return False
    tree = cache.get(relative)
    if tree is None:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=relative)
        cache[relative] = tree
    body: list[ast.stmt] = tree.body
    for raw_name in node_names:
        name = raw_name.split("[", 1)[0]
        node = next(
            (
                candidate
                for candidate in body
                if isinstance(
                    candidate,
                    (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef),
                )
                and candidate.name == name
            ),
            None,
        )
        if node is None:
            return False
        body = node.body if isinstance(node, ast.ClassDef) else []
    return True


def validate_manifest() -> Counter[str]:
    """Validate completeness, uniqueness, dispositions, and live selectors."""
    authoritative = read_case_map()
    rows = read_manifest()
    errors: list[str] = []
    counts = Counter(row.old_selector for row in rows)
    duplicates = sorted(selector for selector, count in counts.items() if count > 1)
    if duplicates:
        errors.append(f"duplicate manifest selectors: {duplicates}")
    manifest_selectors = set(counts)
    missing = sorted(set(authoritative) - manifest_selectors)
    extra = sorted(manifest_selectors - set(authoritative))
    if missing:
        errors.append(f"missing authoritative selectors: {missing}")
    if extra:
        errors.append(f"unknown manifest selectors: {extra}")

    ast_cache: dict[str, ast.Module] = {}
    for row in rows:
        if row.disposition not in ALLOWED_DISPOSITIONS:
            errors.append(
                f"{row.old_selector}: invalid disposition {row.disposition!r}"
            )
        if not row.reason.strip():
            errors.append(f"{row.old_selector}: empty reason")
        if row.disposition in {"active", "strengthened"} and not row.live_selector:
            errors.append(
                f"{row.old_selector}: {row.disposition} requires live_selector"
            )
        if row.disposition == "unresolved" and row.live_selector:
            errors.append(
                f"{row.old_selector}: unresolved row must not claim live_selector"
            )
        if row.live_selector and not selector_exists(row.live_selector, ast_cache):
            errors.append(
                f"{row.old_selector}: missing live selector {row.live_selector}"
            )
    if errors:
        raise ValueError("\n".join(errors))
    if len(rows) != 1458:
        raise ValueError(f"expected 1,458 manifest rows, found {len(rows)}")
    return Counter(row.disposition for row in rows)


def main() -> None:
    """Build on request, always validate, and print disposition counts."""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--build",
        action="store_true",
        help="rebuild the checked-in manifest before validation",
    )
    args = parser.parse_args()
    if args.build:
        build_manifest()
    counts = validate_manifest()
    print(f"validated {sum(counts.values())} legacy selectors")
    for disposition in sorted(ALLOWED_DISPOSITIONS):
        print(f"{disposition}\t{counts[disposition]}")


if __name__ == "__main__":
    main()
