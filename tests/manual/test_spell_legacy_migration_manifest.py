"""Reviewed selector ledger for the spell/spatial slice of the d80 rework."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CASE_MAP = (
    ROOT
    / "agent_docs/research/d80-test-rework-coverage-audit"
    / "d80_case_coverage_map.tsv"
)


@dataclass(frozen=True)
class LegacyCoverage:
    selector: str
    status: str
    rationale: str


def _kept(selector: str, rationale: str) -> LegacyCoverage:
    return LegacyCoverage(
        selector=selector,
        status="strengthened",
        rationale=rationale,
    )


OWNED_OLD_PATHS = frozenset(
    {
        "examples/spatial_events_test.py",
        "examples/test_aoe_convolution.py",
        "examples/test_aoe_integration.py",
        "examples/test_aoe_shapes.py",
        "examples/test_bless_bane.py",
        "examples/test_burning_hands.py",
        "examples/test_cloudkill.py",
        "examples/test_concentration.py",
        "examples/test_concentration_spells.py",
        "examples/test_difficult_terrain.py",
        "examples/test_directional_arena_hotswap.py",
        "examples/test_directional_environment_items.py",
        "examples/test_easy_tier_spells.py",
        "examples/test_entity_blocking.py",
        "examples/test_expeditious_retreat.py",
        "examples/test_fireball.py",
        "examples/test_grease.py",
        "examples/test_gust_of_wind.py",
        "examples/test_hazard_pathfinding.py",
        "examples/test_ice_storm.py",
        "examples/test_incendiary_cloud.py",
        "examples/test_insect_plague.py",
        "examples/test_jump_spell.py",
        "examples/test_magic_missile_multi.py",
        "examples/test_mirror_image.py",
        "examples/test_multi_target_allies.py",
        "examples/test_new_spells.py",
        "examples/test_protection.py",
        "examples/test_ray_of_frost_duration.py",
        "examples/test_self_range_aoe_availability.py",
        "examples/test_shield_spell.py",
        "examples/test_sleep_color_spray.py",
        "examples/test_spatial_handler_registry.py",
        "examples/test_spell_catalog_api.py",
        "examples/test_spell_crit_dice.py",
        "examples/test_spell_system.py",
        "examples/test_spike_growth.py",
        "examples/test_spike_zone.py",
        "examples/test_spirit_guardians.py",
        "examples/test_sunbeam.py",
        "examples/test_terrain_movement_system.py",
        "examples/test_thunderwave.py",
        "examples/test_tile_condition_duration.py",
        "examples/test_tile_directional_blocking.py",
        "examples/test_web.py",
    }
)

EXTERNALLY_REVIEWED_SELECTOR = (
    "examples/test_gust_of_wind.py::test_gust_terrain_reactive_paths"
)

AOE_SHAPES = (
    "tests/manual/test_aoe_shape_legacy_contract.py::"
    "test_aoe_shapes_preserve_extent_width_entities_and_wall_occlusion"
)
AOE_REGISTRY = (
    "tests/manual/test_aoe_shape_legacy_contract.py::"
    "test_spatial_registry_dispatches_multiple_indexed_and_global_handlers"
)
CLOSE_AREA = (
    "tests/manual/test_remaining_spell_legacy_contract.py::"
    "test_close_area_spells_execute_save_geometry_damage_and_push_rules"
)
FIREBALL_MATRIX = (
    "tests/manual/test_remaining_spell_legacy_contract.py::"
    "test_fireball_executes_save_upcast_relationship_and_aggregation_matrix"
)
FIREBALL_GEOMETRY = (
    "tests/manual/test_remaining_spell_legacy_contract.py::"
    "test_fireball_enforces_cast_los_range_and_explosion_occlusion"
)
THUNDER_BLOCKERS = (
    "tests/manual/test_remaining_spell_legacy_contract.py::"
    "test_thunderwave_push_stops_before_walls_and_occupied_cells"
)
ZONE_GUST = (
    "tests/manual/test_remaining_zone_spell_legacy_contract.py::"
    "test_gust_of_wind_executes_cast_entry_turn_wall_and_cleanup_edges"
)
ZONE_INSECTS = (
    "tests/manual/test_remaining_zone_spell_legacy_contract.py::"
    "test_insect_plague_executes_initial_entry_turn_reentry_and_cleanup"
)
ZONE_INCENDIARY = (
    "tests/manual/test_remaining_zone_spell_legacy_contract.py::"
    "test_incendiary_cloud_executes_initial_entry_turn_move_and_cleanup"
)
TERRAIN_MODE_PATHS = (
    "tests/manual/test_remaining_zone_spell_legacy_contract.py::"
    "test_movement_mode_pathfinding_preserves_terrain_specific_routes"
)
GREASE_LIFECYCLE = (
    "tests/manual/test_remaining_zone_spell_legacy_contract.py::"
    "test_grease_preserves_initial_entry_turn_stand_and_cleanup_rules"
)
CLOUDKILL_LIFECYCLE = (
    "tests/manual/test_remaining_zone_spell_legacy_contract.py::"
    "test_cloudkill_preserves_initial_entry_turn_move_and_cleanup_rules"
)
SPIRIT_GUARDIANS_LIFECYCLE = (
    "tests/manual/test_remaining_zone_spell_legacy_contract.py::"
    "test_spirit_guardians_preserves_faction_damage_slow_follow_and_cleanup"
)
POSITION_AOE_CONVOLUTION = (
    "tests/manual/test_remaining_spell_legacy_contract.py::"
    "test_position_aoe_preview_execution_preserves_filters_and_cardinality"
)
SELF_RANGE_AOE_DISCOVERY = (
    "tests/manual/test_remaining_spell_legacy_contract.py::"
    "test_self_range_aoe_discovery_survives_zero_visible_enemies"
)
HAZARD_CLASSIFICATION = (
    "tests/manual/test_remaining_zone_spell_legacy_contract.py::"
    "test_hazard_filters_and_factions_preserve_exact_requester_semantics"
)
SPIKE_ZONE_ACTIVATION = (
    "tests/manual/test_spike_zone_movement_legacy_contract.py::"
    "test_spike_zone_activation_and_deactivation_are_one_shared_hazard"
)
SPIKE_GROWTH_LIFECYCLE = (
    "tests/manual/test_remaining_zone_spell_legacy_contract.py::"
    "test_spike_growth_preserves_hidden_hazard_damage_and_source_immunity"
)
MAGIC_MISSILE_DISTRIBUTION = (
    "tests/manual/test_remaining_spell_legacy_contract.py::"
    "test_magic_missile_preserves_dart_distribution_upcast_and_enemy_filter"
)


DEFAULT_REPLACEMENTS = {
    "examples/test_aoe_convolution.py": (
        "tests/engine_book/test_chapter_09_action_templates_discovery.py::"
        "test_eb_09_010_registered_position_aoe_spell_previews_and_executes"
    ),
    "examples/test_aoe_integration.py": (
        "tests/engine_book/test_chapter_09_action_templates_discovery.py::"
        "test_eb_09_010_registered_position_aoe_spell_previews_and_executes"
    ),
    "examples/test_aoe_shapes.py": AOE_SHAPES,
    "examples/test_bless_bane.py": (
        "tests/engine_book/test_chapter_15_spell_families.py::"
        "test_eb_15_015_bless_and_bane_rewrite_save_d20_results"
    ),
    "examples/test_burning_hands.py": CLOSE_AREA,
    "examples/test_cloudkill.py": (
        "tests/engine_book/test_chapter_15_spell_families.py::"
        "test_eb_15_021_zone_spell_family_entry_turn_start_and_cleanup_edges"
    ),
    "examples/test_concentration.py": (
        "tests/engine_book/test_chapter_14_spellcasting_core.py::"
        "test_eb_14_010_concentration_links_cleanup_and_empty_casts"
    ),
    "examples/test_concentration_spells.py": (
        "tests/engine_book/test_chapter_15_spell_families.py::"
        "test_eb_15_017_hold_person_failed_save_repeat_save_and_cleanup"
    ),
    "examples/test_difficult_terrain.py": (
        "tests/engine_book/test_chapter_11_grid_tiles_pathfinding.py::"
        "test_eb_11_003_dijkstra_paths_sum_tile_costs_and_can_ignore_difficult_terrain"
    ),
    "examples/test_directional_arena_hotswap.py": (
        "tests/manual/test_directional_environment_legacy_contract.py::"
        "test_live_and_editor_standard_builders_share_directional_barrier_contract"
    ),
    "examples/test_directional_environment_items.py": (
        "tests/manual/test_directional_environment_legacy_contract.py::"
        "test_directional_wall_blocks_only_declared_sides_and_stays_structural"
    ),
    "examples/test_easy_tier_spells.py": (
        "tests/manual/test_remaining_spell_legacy_contract.py::"
        "test_shocking_grasp_damage_scaling_metal_advantage_and_reaction_lifecycle"
    ),
    "examples/test_entity_blocking.py": (
        "tests/engine_book/test_chapter_11_grid_tiles_pathfinding.py::"
        "test_eb_11_005_occupants_and_objects_block_walkable_tiles_polymorphically"
    ),
    "examples/test_expeditious_retreat.py": (
        "tests/manual/test_remaining_spell_legacy_contract.py::"
        "test_expeditious_retreat_grant_cost_discovery_and_concentration_cleanup"
    ),
    "examples/test_fireball.py": FIREBALL_MATRIX,
    "examples/test_grease.py": (
        "tests/engine_book/test_chapter_15_spell_families.py::"
        "test_eb_15_021_zone_spell_family_entry_turn_start_and_cleanup_edges"
    ),
    "examples/test_gust_of_wind.py": ZONE_GUST,
    "examples/test_hazard_pathfinding.py": (
        "tests/engine_book/test_chapter_11_grid_tiles_pathfinding.py::"
        "test_eb_11_008_hazards_can_be_excluded_from_safe_paths"
    ),
    "examples/test_ice_storm.py": (
        "tests/manual/test_138_mixed_damage_spell_contract.py::"
        "test_ice_storm_executes_upcast_save_cylinder_and_terrain_lifecycle"
    ),
    "examples/test_incendiary_cloud.py": ZONE_INCENDIARY,
    "examples/test_insect_plague.py": ZONE_INSECTS,
    "examples/test_jump_spell.py": (
        "tests/manual/test_remaining_spell_legacy_contract.py::"
        "test_jump_spell_composes_modifiers_targets_ally_and_expands_discovery"
    ),
    "examples/test_magic_missile_multi.py": (
        "tests/engine_book/test_chapter_14_spellcasting_core.py::"
        "test_eb_14_008_magic_missile_convolution_aggregates_child_casts"
    ),
    "examples/test_mirror_image.py": (
        "tests/engine_book/test_chapter_15_spell_families.py::"
        "test_eb_15_019_mirror_image_duplicates_absorb_missed_attacks"
    ),
    "examples/test_multi_target_allies.py": (
        "tests/manual/test_remaining_spell_legacy_contract.py::"
        "test_multi_target_ally_filter_is_unique_bounded_and_atomic"
    ),
    "examples/test_new_spells.py": (
        "tests/manual/test_remaining_spell_legacy_contract.py::"
        "test_ray_of_frost_hit_and_slow_expire_on_caster_turn_not_target_turn"
    ),
    "examples/test_protection.py": (
        "tests/manual/test_protection_reaction_legacy_contract.py::"
        "test_protection_imposes_disadvantage_once_and_consumes_reaction"
    ),
    "examples/test_ray_of_frost_duration.py": (
        "tests/manual/test_remaining_spell_legacy_contract.py::"
        "test_ray_of_frost_hit_and_slow_expire_on_caster_turn_not_target_turn"
    ),
    "examples/test_self_range_aoe_availability.py": (
        "tests/engine_book/test_chapter_09_action_templates_discovery.py::"
        "test_eb_09_010_registered_position_aoe_spell_previews_and_executes"
    ),
    "examples/test_shield_spell.py": (
        "tests/engine_book/test_chapter_15_spell_families.py::"
        "test_eb_15_009_shield_reaction_converts_marginal_attack_hit_to_miss"
    ),
    "examples/test_sleep_color_spray.py": (
        "tests/engine_book/test_chapter_15_spell_families.py::"
        "test_eb_15_013_sleep_hp_pool_selection_immunity_and_wake_on_damage"
    ),
    "examples/test_spatial_handler_registry.py": AOE_REGISTRY,
    "examples/test_spell_catalog_api.py": (
        "tests/engine_book/test_chapter_14_spellcasting_core.py::"
        "test_eb_14_017_spell_catalog_identity_matches_spell_events"
    ),
    "examples/test_spell_crit_dice.py": (
        "tests/manual/test_spell_critical_dice_legacy_contract.py::"
        "test_spell_attack_critical_rolls_double_once"
    ),
    "examples/test_spell_system.py": (
        "tests/engine_book/test_chapter_14_spellcasting_core.py::"
        "test_eb_14_004_spell_actions_create_spell_events_and_slot_costs"
    ),
    "examples/test_spike_growth.py": (
        "tests/manual/test_14_spell_families.py::"
        "test_zone_spell_family_owns_spatial_handlers_and_concentration_cleanup"
    ),
    "examples/test_spike_zone.py": (
        "tests/manual/test_spike_zone_movement_legacy_contract.py::"
        "test_spike_zone_applies_damage_for_each_committed_step"
    ),
    "examples/test_spirit_guardians.py": (
        "tests/engine_book/test_chapter_15_spell_families.py::"
        "test_eb_15_021_zone_spell_family_entry_turn_start_and_cleanup_edges"
    ),
    "examples/test_sunbeam.py": (
        "tests/manual/test_remaining_spell_legacy_contract.py::"
        "test_sunbeam_initial_and_repeat_line_share_concentration_owned_action"
    ),
    "examples/test_terrain_movement_system.py": (
        "tests/engine_book/test_chapter_11_grid_tiles_pathfinding.py::"
        "test_eb_11_003_dijkstra_paths_sum_tile_costs_and_can_ignore_difficult_terrain"
    ),
    "examples/test_thunderwave.py": CLOSE_AREA,
    "examples/test_tile_condition_duration.py": (
        "tests/manual/test_tile_condition_duration_legacy_contract.py::"
        "test_tile_duration_expiry_removes_owned_cross_block_effect"
    ),
    "examples/test_tile_directional_blocking.py": (
        "tests/manual/test_directional_environment_legacy_contract.py::"
        "test_directional_wall_blocks_only_declared_sides_and_stays_structural"
    ),
    "examples/test_web.py": (
        "tests/engine_book/test_chapter_15_spell_families.py::"
        "test_eb_15_029_web_models_obscurement_grounding_and_escape_cleanup"
    ),
}


def _special(old_selector: str) -> LegacyCoverage | None:
    path, name = old_selector.split("::", 1)
    deterministic = (
        "The archived case used stochastic rolls, print-only checks, a soft "
        "custom runner, or a narrower assertion. The maintained selector "
        "executes the same rule with deterministic outcomes and hard assertions."
    )

    if path == "examples/spatial_events_test.py":
        selectors = {
            "test_gridmap_basics": (
                "tests/engine_book/test_chapter_11_grid_tiles_pathfinding.py::"
                "test_eb_11_001_tiles_are_grid_stored_blocks_with_uuid_lookup"
            ),
            "test_entity_registration": (
                "tests/manual/test_08_world_model_and_movement.py::"
                "test_entity_position_index_and_spatial_events_follow_grid_moves"
            ),
            "test_spatial_events_on_movement": (
                "tests/manual/test_08_world_model_and_movement.py::"
                "test_entity_position_index_and_spatial_events_follow_grid_moves"
            ),
            "test_cell_subscriptions": (
                "tests/engine_book/test_chapter_12_senses_light_stealth.py::"
                "test_eb_12_004_light_change_reveals_subscribed_dark_cells_reactively"
            ),
            "test_fov_integration": (
                "tests/engine_book/test_chapter_11_grid_tiles_pathfinding.py::"
                "test_eb_11_022_fov_cache_invalidates_when_vision_blockers_change"
            ),
            "test_pathfinding_integration": (
                "tests/engine_book/test_chapter_11_grid_tiles_pathfinding.py::"
                "test_eb_11_003_dijkstra_paths_sum_tile_costs_and_can_ignore_difficult_terrain"
            ),
            "test_entity_senses_with_gridmap": (
                "tests/engine_book/test_chapter_12_senses_light_stealth.py::"
                "test_eb_12_001_geometric_fov_is_filtered_by_effective_light"
            ),
            "test_no_duplicate_events": (
                "tests/manual/test_08_world_model_and_movement.py::"
                "test_entity_position_index_and_spatial_events_follow_grid_moves"
            ),
            "test_tile_change_events": (
                "tests/manual/test_08_world_model_and_movement.py::"
                "test_directional_border_blocks_transition_and_emits_tile_change"
            ),
            "test_multiple_entities_movement": (
                "tests/manual/test_08_world_model_and_movement.py::"
                "test_entity_position_index_and_spatial_events_follow_grid_moves"
            ),
        }
        return _kept(selectors[name], deterministic)

    if old_selector == (
        "examples/test_aoe_integration.py::test_dead_entity_filtering"
    ):
        return _kept(
            "tests/engine_book/test_chapter_09_action_templates_discovery.py::"
            "test_eb_09_008_target_filters_and_dead_targets_shape_entity_actions",
            deterministic,
        )

    if path == "examples/test_aoe_convolution.py" or old_selector == (
        "examples/test_aoe_integration.py::test_position_aoe_in_available_actions"
    ):
        return _kept(
            POSITION_AOE_CONVOLUTION,
            (
                "The maintained regression proves include-self true and false, "
                "enemy-only filtering, deterministic target order and "
                "cardinality, per-target convolution, aggregated damage, and "
                "preview-to-execution target identity."
            ),
        )

    if path == "examples/test_self_range_aoe_availability.py":
        return _kept(
            SELF_RANGE_AOE_DISCOVERY,
            (
                "The maintained regression registers real cone, cube, line, "
                "and ranged AoE spells, proves all remain discoverable with "
                "zero enemies, and then proves a visible enemy populates the "
                "self-range preview."
            ),
        )

    if path == "examples/test_bless_bane.py":
        if name in {
            "test_bane_concentration_break",
            "test_bless_concentration_break",
            "test_multi_target_counts",
        }:
            return _kept(
                "tests/engine_book/test_chapter_15_spell_families.py::"
                "test_eb_15_005_multi_target_concentration_links_each_effect",
                deterministic,
            )
        if name.startswith("test_necrotic_bless"):
            return _kept(
                "tests/manual/test_remaining_spell_legacy_contract.py::"
                "test_necrotic_bless_executes_undead_failure_and_success_branches",
                deterministic,
            )

    if path == "examples/test_concentration.py":
        if name in {
            "test_2_concentration_check_pass",
            "test_3_concentration_check_fail_high_damage",
        }:
            return _kept(
                "tests/engine_book/test_chapter_14_spellcasting_core.py::"
                "test_eb_14_015_damage_and_death_break_concentration_deterministically",
                deterministic,
            )
        if name in {
            "test_7_multi_slot_concentration",
            "test_10_multi_slot_zero_children_cleanup",
        }:
            return _kept(
                "tests/engine_book/test_chapter_14_spellcasting_core.py::"
                "test_eb_14_014_drop_concentration_can_target_one_multi_slot_spell",
                deterministic,
            )
        if name == "test_8_twinned_spell_single_concentrating":
            return _kept(
                "tests/engine_book/test_chapter_14_spellcasting_core.py::"
                "test_eb_14_016_multi_target_concentration_reuses_one_slot",
                deterministic,
            )

    if path == "examples/test_concentration_spells.py":
        if "call_lightning" in name:
            return _kept(
                "tests/manual/test_remaining_spell_legacy_contract.py::"
                "test_call_lightning_grants_repeatable_strike_and_cleans_on_replacement",
                deterministic,
            )
        if name == "test_6_concentration_broken_by_damage":
            return _kept(
                "tests/engine_book/test_chapter_14_spellcasting_core.py::"
                "test_eb_14_015_damage_and_death_break_concentration_deterministically",
                deterministic,
            )

    if path == "examples/test_difficult_terrain.py":
        selectors = {
            "test_tile_movement_costs": (
                "tests/engine_book/test_chapter_11_grid_tiles_pathfinding.py::"
                "test_eb_11_002_tile_movement_modes_define_walkability"
            ),
            "test_tile_borders": (
                "tests/engine_book/test_chapter_11_grid_tiles_pathfinding.py::"
                "test_eb_11_006_directional_borders_block_transitions_and_emit_metadata"
            ),
            "test_tile_uuid_lookup": (
                "tests/engine_book/test_chapter_11_grid_tiles_pathfinding.py::"
                "test_eb_11_001_tiles_are_grid_stored_blocks_with_uuid_lookup"
            ),
            "test_move_action_uses_terrain_costs": (
                "tests/engine_book/test_chapter_11_grid_tiles_pathfinding.py::"
                "test_eb_11_004_move_action_converts_tile_cost_units_to_feet"
            ),
        }
        if name in selectors:
            return _kept(selectors[name], deterministic)

    if path == "examples/test_directional_environment_items.py":
        if "door" in name:
            return _kept(
                "tests/manual/test_directional_environment_legacy_contract.py::"
                "test_directional_door_open_event_preserves_other_sides_and_rejects_close_occupancy",
                deterministic,
            )
        if "forced_movement" in name:
            return _kept(
                "tests/manual/test_directional_environment_legacy_contract.py::"
                "test_directional_propagation_wall_removes_threat_and_opportunity_attack",
                deterministic,
            )
        if "hidden" in name:
            return _kept(
                "tests/engine_book/test_chapter_12_senses_light_stealth.py::"
                "test_eb_12_015_hidden_cell_blocker_reveals_on_movement_collision",
                deterministic,
            )

    if path == "examples/test_easy_tier_spells.py":
        if "guiding_bolt" in name:
            if name == "test_guiding_bolt_mark_duration_expiration":
                return LegacyCoverage(
                    selector=(
                        "tests/manual/test_remaining_spell_legacy_contract.py::"
                        "test_guiding_bolt_actual_cast_expires_at_end_of_casters_next_turn"
                    ),
                    status="stale",
                    rationale=(
                        "The old fixture manually attached a target-ticked duration, "
                        "contradicting the rule. The replacement executes the real "
                        "spell and expires on the caster's next-turn boundary."
                    ),
                )
            return _kept(
                "tests/manual/test_remaining_spell_legacy_contract.py::"
                "test_guiding_bolt_hit_upcast_mark_and_first_attack_cleanup",
                deterministic,
            )
        if "power_word_stun" in name:
            return _kept(
                "tests/manual/test_remaining_spell_legacy_contract.py::"
                "test_power_word_stun_threshold_range_and_repeat_save_cleanup",
                deterministic,
            )

    if path == "examples/test_entity_blocking.py" and (
        "dead" in name or "dead_body" in name
    ):
        return _kept(
            "tests/engine_book/test_chapter_11_grid_tiles_pathfinding.py::"
            "test_eb_11_015_dead_entities_become_non_blocking_for_paths",
            deterministic,
        )

    if path == "examples/test_fireball.py" and name in {
        "test_fireball_los_requirement",
        "test_fireball_range_validation",
        "test_fireball_aoe_behind_walls",
    }:
        return _kept(FIREBALL_GEOMETRY, deterministic)

    if path == "examples/test_hazard_pathfinding.py":
        if name in {
            "test_a1_no_hazard_filter",
            "test_a2_hazard_filter_all",
            "test_a3_hazard_filter_non_source",
            "test_a4_hazard_filter_enemies",
            "test_b_is_enemy_of",
            "test_c_gridmap_hazardous",
        }:
            return _kept(
                HAZARD_CLASSIFICATION,
                (
                    "The maintained regression proves none, ALL, NON_SOURCE, "
                    "and ENEMIES hazard filters for source, ally, enemy, "
                    "neutral, and anonymous requesters, plus entity and tile "
                    "faction semantics and GridMap delegation."
                ),
            )
        if "hidden" in name or "stealth_dc" in name:
            return _kept(
                "tests/engine_book/test_chapter_11_grid_tiles_pathfinding.py::"
                "test_eb_11_014_hidden_hazard_perception_change_recomputes_safe_paths",
                deterministic,
            )
        if name == "test_d_spike_trap_rework":
            return _kept(
                SPIKE_ZONE_ACTIVATION,
                (
                    "The maintained regression installs the returned floor "
                    "tiles, proves one shared handler and hazardous markers, "
                    "then deactivates and verifies every marker, handler index, "
                    "and hazard classification is gone."
                ),
            )
        if "zone_removal" in name or "spike_growth_markers" in name:
            return _kept(
                SPIKE_GROWTH_LIFECYCLE,
                (
                    "The maintained regression casts real Spike Growth and "
                    "proves its NON_SOURCE hidden marker, perception gate, "
                    "terrain, entry damage, caster immunity, and concentration "
                    "cleanup."
                ),
            )
        if name == "test_f_no_hazard_no_safe_paths":
            return _kept(HAZARD_CLASSIFICATION, deterministic)
        if "auto_safe_movement" in name:
            return _kept(
                "tests/engine_book/test_chapter_09_action_templates_discovery.py::"
                "test_eb_09_011_move_discovery_marks_hazardous_and_safe_paths",
                (
                    "The maintained action-discovery regression exposes both "
                    "paths, executes with prefer_safe=True, and proves the "
                    "committed route and movement cost equal the safe preview."
                ),
            )

    if path == "examples/test_mirror_image.py" and (
        "duration" in name or "applies" in name
    ):
        return _kept(
            "tests/engine_book/test_chapter_15_spell_families.py::"
            "test_eb_15_035_mirror_image_recast_replaces_and_duration_expires",
            deterministic,
        )

    if path == "examples/test_magic_missile_multi.py":
        return _kept(
            MAGIC_MISSILE_DISTRIBUTION,
            (
                "The maintained regression executes repeated single-target, "
                "split-target, and upcast dart distributions with exact "
                "per-dart damage, and proves ally rejection preserves action "
                "and slot resources."
            ),
        )

    if path == "examples/test_new_spells.py":
        groups = (
            (
                ("acid_splash",),
                "test_acid_splash_two_target_damage_and_proximity_validation",
            ),
            (
                ("scorching_ray",),
                "test_scorching_ray_executes_every_base_and_upcast_projectile",
            ),
            (
                ("blur", "blindness_deafness"),
                "test_blur_and_blindness_deafness_execute_distinct_lifecycles",
            ),
            (
                ("fear", "hypnotic_pattern"),
                "test_fear_and_hypnotic_pattern_execute_area_and_cleanup_rules",
            ),
        )
        for tokens, live_name in groups:
            if any(token in name for token in tokens):
                return _kept(
                    f"tests/manual/test_remaining_spell_legacy_contract.py::{live_name}",
                    deterministic,
                )
        if "misty_step" in name:
            return _kept(
                "tests/engine_book/test_manual_17_spell_families.py::"
                "test_movement_family_misty_step_teleports_and_uses_bonus_action",
                deterministic,
            )

    if path == "examples/test_protection.py" and name != "test_basic_protection":
        return _kept(
            "tests/manual/test_protection_reaction_legacy_contract.py::"
            "test_protection_rejects_each_ineligible_reaction_gate",
            deterministic,
        )

    if path == "examples/test_shield_spell.py":
        if "disabled" in name:
            return _kept(
                "tests/engine_book/test_chapter_15_spell_families.py::"
                "test_eb_15_022_shield_handler_toggle_gates_attack_and_missile_reactions",
                deterministic,
            )
        if "mm" in name or "darts" in name:
            return _kept(
                "tests/engine_book/test_chapter_15_spell_families.py::"
                "test_eb_15_010_shield_blocks_magic_missile_darts_against_its_target_only",
                deterministic,
            )
        if any(
            token in name
            for token in (
                "does_not_fire",
                "no_reaction",
                "no_spell_slots",
                "persists",
                "stacking",
                "refires",
                "only_fires_once",
            )
        ):
            return _kept(
                "tests/engine_book/test_chapter_15_spell_families.py::"
                "test_eb_15_020_shield_non_firing_persistence_and_turn_cleanup",
                deterministic,
            )

    if path == "examples/test_sleep_color_spray.py":
        if "color_spray" in name:
            return _kept(
                "tests/engine_book/test_chapter_15_spell_families.py::"
                "test_eb_15_014_color_spray_hp_pool_skips_and_blinded_cleanup",
                deterministic,
            )
        if "upcast" in name or "empty" in name or "skip_high" in name:
            return _kept(
                "tests/engine_book/test_chapter_15_spell_families.py::"
                "test_eb_15_030_hp_pool_spells_cover_upcast_and_immunity_edges",
                deterministic,
            )

    if old_selector == (
        "examples/test_spell_catalog_api.py::test_catalog_endpoint"
    ):
        return _kept(
            "tests/engine_book/test_chapter_18_encounters_apis.py::"
            "test_eb_18_006_serialization_and_spell_catalog_api_do_not_mutate_registry",
            deterministic,
        )

    if path == "examples/test_spell_system.py":
        if name == "test_magic_missile_dart_count":
            return _kept(MAGIC_MISSILE_DISTRIBUTION, deterministic)
        groups = {
            "test_spell_slots_in_action_economy": "test_eb_14_001_spell_slots_are_action_economy_values",
            "test_spellcasting_block_fields": "test_eb_14_002_spellcasting_block_is_modifier_only",
            "test_entity_spell_methods": "test_eb_14_003_entity_spell_numbers_compose_from_multiple_blocks",
            "test_modifier_stacking": "test_eb_14_003_entity_spell_numbers_compose_from_multiple_blocks",
            "test_non_caster_defaults": "test_eb_14_002_spellcasting_block_is_modifier_only",
            "test_fire_bolt_cantrip_scaling": "test_eb_14_005_cantrip_dice_scale_at_srd_thresholds",
            "test_cantrip_variant_generation": "test_eb_14_006_generate_variants_uses_available_slots",
            "test_leveled_spell_variant_generation": "test_eb_14_006_generate_variants_uses_available_slots",
            "test_fire_bolt_combat": "test_eb_15_002_evocation_attack_save_and_area_damage_patterns",
            "test_magic_missile_combat": "test_magic_missile_auto_hits_multiple_darts_and_spends_slot",
            "test_spell_slot_consumption": "test_eb_14_004_spell_actions_create_spell_events_and_slot_costs",
            "test_spell_slot_pipeline": "test_eb_14_004_spell_actions_create_spell_events_and_slot_costs",
        }
        if name in groups:
            file_name = (
                "tests/engine_book/test_chapter_15_spell_families.py"
                if groups[name].startswith("test_eb_15")
                else (
                    "tests/engine_book/test_manual_16_spellcasting_core.py"
                    if groups[name].startswith("test_magic_missile_auto")
                    else "tests/engine_book/test_chapter_14_spellcasting_core.py"
                )
            )
            return _kept(f"{file_name}::{groups[name]}", deterministic)
        if name in {"test_include_self_targeting", "test_mage_armor_self_cast"}:
            return _kept(
                "tests/engine_book/test_chapter_09_action_templates_discovery.py::"
                "test_eb_09_008_target_filters_and_dead_targets_shape_entity_actions",
                deterministic,
            )
        if name == "test_mage_armor_ends_on_armor_equip":
            return _kept(
                "tests/engine_book/test_chapter_15_spell_families.py::"
                "test_eb_15_004_abjuration_buffs_and_restoration_remove_conditions",
                deterministic,
            )
        if name == "test_sacred_flame_combat":
            return _kept(
                "tests/engine_book/test_chapter_15_spell_families.py::"
                "test_eb_15_002_evocation_attack_save_and_area_damage_patterns",
                deterministic,
            )

    if path == "examples/test_cloudkill.py":
        return _kept(
            CLOUDKILL_LIFECYCLE,
            (
                "The maintained regression verifies initial, entry, and "
                "turn-start poison damage with deterministic dice, the exact "
                "10-foot automatic move, normal terrain, and complete "
                "concentration cleanup."
            ),
        )

    if path == "examples/test_grease.py":
        return _kept(
            GREASE_LIFECYCLE,
            (
                "The maintained regression casts Grease over an initial "
                "occupant, forces an off-turn entry, proves owner-turn "
                "auto-stand spends exactly half movement, proves zero movement "
                "retains Prone, and verifies concentration removes the zone "
                "and difficult terrain."
            ),
        )

    if path == "examples/test_spike_zone.py":
        if name in {
            "test_death_stops_movement",
            "test_paths_dirty_cleared_on_early_exit",
        }:
            return _kept(
                "tests/manual/test_spike_zone_movement_legacy_contract.py::"
                "test_lethal_spike_step_stops_remaining_movement_with_life_state",
                deterministic,
            )

        if name == "test_dead_condition_applied_on_spike_death":
            return LegacyCoverage(
                selector=(
                    "tests/manual/test_spike_zone_movement_legacy_contract.py::"
                    "test_lethal_spike_step_stops_remaining_movement_with_life_state"
                ),
                status="stale",
                rationale=(
                    "Dead conditions were deliberately removed. Health.life_state "
                    "is authoritative; the maintained regression asserts DEAD and "
                    "also proves no legacy Dead condition is manufactured."
                ),
            )
        if name == "test_paths_updated_after_move":
            return _kept(
                "tests/engine_book/test_chapter_12_senses_light_stealth.py::"
                "test_eb_12_008_self_movement_updates_visibility_and_marks_paths_dirty",
                deterministic,
            )

    if path == "examples/test_spike_growth.py":
        return _kept(
            SPIKE_GROWTH_LIFECYCLE,
            (
                "The maintained regression casts real Spike Growth and proves "
                "zone terrain, per-entry damage, source immunity, hidden hazard "
                "semantics, and concentration cleanup."
            ),
        )

    if path == "examples/test_spirit_guardians.py":
        return _kept(
            SPIRIT_GUARDIANS_LIFECYCLE,
            (
                "The maintained regression verifies initial enemy damage and "
                "ally exclusion, once-per-turn entry damage, exact speed "
                "halving and restoration, caster-following geometry, and "
                "concentration cleanup."
            ),
        )

    if path == "examples/test_terrain_movement_system.py":
        if name in {
            "test_flying_pathfinding_ignores_difficult_terrain",
            "test_flying_pathfinding_blocked_by_walls",
            "test_swimming_pathfinding_through_water",
            "test_swimming_blocked_on_land",
            "test_walking_blocked_by_water",
            "test_mixed_terrain_path_cost",
        }:
            return _kept(
                TERRAIN_MODE_PATHS,
                (
                    "The maintained regression executes compute_paths for "
                    "walking, flying, and swimming across difficult terrain, "
                    "solid walls, water, and land."
                ),
            )
        if "border" in name or "diagonal" in name:
            return _kept(
                "tests/engine_book/test_chapter_11_grid_tiles_pathfinding.py::"
                "test_eb_11_021_diagonal_transitions_need_one_cardinal_bridge_route",
                deterministic,
            )
        if name == "test_tile_effect_entry_damage":
            return _kept(
                "tests/manual/test_spike_zone_movement_legacy_contract.py::"
                "test_spike_zone_applies_damage_for_each_committed_step",
                (
                    "The maintained regression commits real movement through "
                    "position-indexed tile damage and proves one damage entry "
                    "for every entered hazard cell."
                ),
            )
        if name == "test_tile_effect_turn_start_damage":
            return _kept(
                CLOUDKILL_LIFECYCLE,
                (
                    "The maintained regression places a creature in a real "
                    "turn-start damage zone and asserts exact deterministic "
                    "damage when its TURN_START effect is published."
                ),
            )
        if name == "test_concentration_break_removes_zone":
            return _kept(SPIKE_GROWTH_LIFECYCLE, deterministic)
        if name in {
            "test_tile_effect_adds_difficult_terrain",
            "test_tile_effect_cleanup_on_removal",
            "test_zone_control_computes_affected_positions",
            "test_zone_control_applies_tile_effects",
            "test_zone_control_cleanup_removes_all_effects",
            "test_zone_move_updates_affected_tiles",
        }:
            return _kept(
                "tests/engine_book/test_chapter_11_grid_tiles_pathfinding.py::"
                "test_eb_11_020_zone_removal_cleans_spatial_handlers_terrain_and_markers",
                (
                    "The maintained generic zone regression asserts the exact "
                    "footprint, difficult-terrain modifiers, shared handler and "
                    "markers, old/new movement deltas, and full removal cleanup."
                ),
            )
        if name == "test_entry_damage_on_each_step":
            return _kept(
                "tests/manual/test_spike_zone_movement_legacy_contract.py::"
                "test_spike_zone_applies_damage_for_each_committed_step",
                deterministic,
            )

    if path == "examples/test_thunderwave.py" and name in {
        "test_thunderwave_push_blocked_by_wall",
        "test_thunderwave_push_into_occupied_space",
    }:
        return _kept(THUNDER_BLOCKERS, deterministic)

    if (
        old_selector
        == "examples/test_tile_condition_duration.py::test_environment_step_in_encounter"
    ):
        return _kept(
            "tests/manual/test_tile_condition_duration_legacy_contract.py::"
            "test_encounter_round_boundary_advances_tile_durations",
            deterministic,
        )

    if path == "examples/test_tile_directional_blocking.py":
        if "event_metadata" in name or "serialization" in name:
            return _kept(
                "tests/engine_book/test_chapter_18_encounters_apis.py::"
                "test_eb_18_007_objective_event_frames_preserve_directional_spatial_fields",
                deterministic,
            )
        if "hidden" in name:
            return _kept(
                "tests/engine_book/test_chapter_12_senses_light_stealth.py::"
                "test_eb_12_015_hidden_cell_blocker_reveals_on_movement_collision",
                deterministic,
            )
        if "forced_movement" in name:
            return _kept(
                "tests/engine_book/test_chapter_11_grid_tiles_pathfinding.py::"
                "test_eb_11_017_forced_movement_and_jump_respect_directional_blockers",
                deterministic,
            )
        if "threat" in name:
            return _kept(
                "tests/manual/test_directional_environment_legacy_contract.py::"
                "test_directional_propagation_wall_removes_threat_and_opportunity_attack",
                deterministic,
            )

    if path == "examples/test_web.py" and (
        "concentration" in name or "zone_creation" in name
    ):
        return _kept(
            "tests/engine_book/test_chapter_15_spell_families.py::"
            "test_eb_15_021_zone_spell_family_entry_turn_start_and_cleanup_edges",
            deterministic,
        )

    return None


def _authoritative_owned_selectors() -> list[str]:
    with CASE_MAP.open(encoding="utf-8", newline="") as handle:
        return [
            row["old_selector"]
            for row in csv.DictReader(handle, delimiter="\t")
            if row["old_selector"].split("::", 1)[0] in OWNED_OLD_PATHS
        ]


def _build_ledger() -> dict[str, LegacyCoverage]:
    ledger: dict[str, LegacyCoverage] = {}
    reason = (
        "The maintained replacement executes the archived behavior with legal "
        "fixtures, deterministic outcomes, and hard assertions."
    )
    for old_selector in _authoritative_owned_selectors():
        if old_selector == EXTERNALLY_REVIEWED_SELECTOR:
            continue
        replacement = _special(old_selector)
        if replacement is None:
            old_path = old_selector.split("::", 1)[0]
            replacement = _kept(DEFAULT_REPLACEMENTS[old_path], reason)
        ledger[old_selector] = replacement
    return ledger


SPELL_SPATIAL_LEGACY_CASES = _build_ledger()


def test_spell_spatial_manifest_accounts_for_all_375_owned_cases() -> None:
    """Every assigned selector has a reviewed outcome; one is root-owned already."""
    authoritative = set(_authoritative_owned_selectors())

    assert len(OWNED_OLD_PATHS) == 45
    assert len(authoritative) == 375
    assert EXTERNALLY_REVIEWED_SELECTOR in authoritative
    assert set(SPELL_SPATIAL_LEGACY_CASES) == (
        authoritative - {EXTERNALLY_REVIEWED_SELECTOR}
    )
    assert len(SPELL_SPATIAL_LEGACY_CASES) == 374
    assert {
        row.status
        for row in SPELL_SPATIAL_LEGACY_CASES.values()
    } == {"strengthened", "stale"}
    assert all(row.selector for row in SPELL_SPATIAL_LEGACY_CASES.values())
    assert all(row.rationale for row in SPELL_SPATIAL_LEGACY_CASES.values())
