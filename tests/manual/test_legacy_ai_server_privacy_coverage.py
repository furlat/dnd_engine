"""Exact coverage ledger for displaced AI, server, and privacy cases.

This is intentionally a test-owned manifest rather than a prose estimate.  It
keeps every selected D80 logical case accountable after the old subprocess
scripts, broad objective endpoints, and ``TacticalState`` façade were retired.
"""

from __future__ import annotations

import ast
import csv
from dataclasses import dataclass
from enum import Enum
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
D80_MAP = (
    ROOT
    / "agent_docs"
    / "research"
    / "d80-test-rework-coverage-audit"
    / "d80_case_coverage_map.tsv"
)


class CoverageDisposition(str, Enum):
    """Disposition of one displaced logical case."""

    ACTIVE = "active"
    STRENGTHENED = "strengthened"
    STALE = "stale"
    RETIRED = "retired"


@dataclass(frozen=True)
class LegacyCaseCoverage:
    """One exact old selector and its maintained architectural disposition."""

    old_selector: str
    disposition: CoverageDisposition
    replacements: tuple[str, ...]
    rationale: str


def _row(
    path: str,
    case: str,
    disposition: CoverageDisposition,
    replacement: str,
    rationale: str,
) -> LegacyCaseCoverage:
    """Build one exact manifest row."""
    return LegacyCaseCoverage(
        old_selector=f"{path}::{case}",
        disposition=disposition,
        replacements=(replacement,),
        rationale=rationale,
    )


S = CoverageDisposition.STRENGTHENED
A = CoverageDisposition.ACTIVE
T = CoverageDisposition.STALE
R = CoverageDisposition.RETIRED

LEGACY_CASES = (
    # The TacticalState/old behavior-tree façade is deliberately not revived.
    _row(
        "examples/ai/test_ai_framework.py",
        "test_tactical_state_construction",
        R,
        "tests/manual/test_28_subjective_observation_stream.py::test_ai_observation_snapshot_contains_subjective_data",
        "TacticalState was retired; the replacement proves controlled identity, "
        "turn ownership, observer visibility, and typed visible-entity facts "
        "without claiming the removed facade's helper fields.",
    ),
    _row(
        "examples/ai/test_ai_framework.py",
        "test_tactical_state_action_economy",
        S,
        "tests/manual/test_31_subjective_runtime_epochs.py::test_epoch_rows_have_stable_row_ids_and_action_economy",
        "Typed epoch rows preserve action economy without a parallel tactical DTO.",
    ),
    _row(
        "examples/ai/test_ai_framework.py",
        "test_ev_computation",
        S,
        "tests/manual/test_44_typed_agent_policy.py::test_exact_damage_estimate_preserves_unknown_defenses_and_known_affinities",
        "Expected value now uses typed subjective outcome evidence and unknown-state bounds.",
    ),
    _row(
        "examples/ai/test_ai_framework.py",
        "test_execute_action",
        S,
        "tests/ai/test_live_ai_matchups.py::test_real_socket_native_external_and_external_external_matrix",
        "Execution now crosses the same registered-provider assignment and typed "
        "epoch command boundaries used by live agents.",
    ),
    _row(
        "examples/ai/test_ai_framework.py",
        "test_behavior_tree_agent",
        S,
        "tests/manual/test_44_typed_agent_policy.py::test_shared_behavior_tree_traces_guarded_branch_selection",
        "The shared policy tree exposes deterministic guarded traces instead of a second agent façade.",
    ),
    _row(
        "examples/ai/test_ai_framework.py",
        "test_move_and_attack_composite",
        S,
        "tests/manual/test_48_policy_host.py::test_policy_host_revalidates_one_move_then_resolves_fresh_attack_row",
        "Move-then-attack now revalidates the post-move epoch instead of retaining stale action objects.",
    ),
    _row(
        "examples/ai/test_ai_framework.py",
        "test_interrupt_detection",
        S,
        "tests/manual/test_91_candidate_commitments.py::test_low_hp_survival_is_explicit_interrupt_not_goal_erasure",
        "Interrupts are typed commitment transitions with explicit survival evidence.",
    ),
    _row(
        "examples/ai/test_ai_framework.py",
        "test_utility_scorer",
        S,
        "tests/manual/test_44_typed_agent_policy.py::test_utility_selector_evaluates_every_branch_before_selecting",
        "The shared utility arbiter evaluates all disclosed candidates deterministically.",
    ),
    _row(
        "examples/ai/test_ai_framework.py",
        "test_ai_controller_integration",
        S,
        "tests/ai/test_live_ai_matchups.py::test_real_socket_native_external_and_external_external_matrix",
        "The maintained real-socket matchup drives native and external faction "
        "controllers through isolated registered assignments and accepted typed "
        "epoch commands.",
    ),
    _row(
        "examples/ai/test_ai_framework.py",
        "test_find_move_helpers",
        R,
        "tests/manual/test_48_policy_host.py::test_policy_host_revalidates_one_move_then_resolves_fresh_attack_row",
        "Private move-away and name-lookup convenience helpers were retired. "
        "The replacement covers the surviving runtime behavior: choose an "
        "approach row, execute it, then resolve a fresh legal attack row.",
    ),

    # Successful canonical HTTP paths restored alongside the maintained errors.
    _row(
        "examples/server_tests/test_aoe_api.py",
        "test_aoe_via_api",
        S,
        "tests/engine/test_manual_21_arena_game_sessions_client_state.py::test_aoe_spell_executes_through_canonical_action_and_replication_routes",
        "Fireball now proves discovery, one action route, reducer frames, presentation, and combat log delivery.",
    ),
    _row(
        "examples/server_tests/test_equipment_api.py",
        "test_get_equipment",
        R,
        "tests/engine/test_encounter_apis.py::test_eb_18_036_equipment_mutations_acknowledge_and_replicate_loadout",
        "The broad equipment read was retired; controlled equipment is bootstrap/patch-owned.",
    ),
    _row(
        "examples/server_tests/test_equipment_api.py",
        "test_get_item_detail",
        R,
        "tests/manual/test_113_subjective_replication_routes.py::test_openapi_has_exactly_one_player_replication_route_family",
        "The sideways item-detail state route was deliberately removed from the player surface.",
    ),
    _row(
        "examples/server_tests/test_equipment_api.py",
        "test_equippable_items",
        S,
        "tests/engine/test_encounter_apis.py::test_eb_18_012_equipment_errors_report_slots_inventory_and_loadout",
        "The session-bound affordance read asserts the exact entity, candidate names, slots, and displaced-item response shape.",
    ),
    _row(
        "examples/server_tests/test_equipment_api.py",
        "test_equip",
        S,
        "tests/engine/test_encounter_apis.py::test_eb_18_036_equipment_mutations_acknowledge_and_replicate_loadout",
        "Equip returns a minimal command acknowledgement and state only through canonical patches.",
    ),
    _row(
        "examples/server_tests/test_equipment_api.py",
        "test_unequip",
        S,
        "tests/engine/test_encounter_apis.py::test_eb_18_036_equipment_mutations_acknowledge_and_replicate_loadout",
        "Unequip returns a minimal command acknowledgement and state only through canonical patches.",
    ),
    _row(
        "examples/server_tests/test_equipment_api.py",
        "test_errors",
        S,
        "tests/engine/test_encounter_apis.py::test_eb_18_012_equipment_errors_report_slots_inventory_and_loadout",
        "Typed equipment errors preserve correction metadata without embedding replica state.",
    ),
    _row(
        "examples/server_tests/test_equipment_api.py",
        "test_entity_full",
        R,
        "tests/manual/test_113_subjective_replication_routes.py::test_openapi_has_exactly_one_player_replication_route_family",
        "The broad entity-full endpoint was retired in favor of the perspective-safe replica.",
    ),
    _row(
        "examples/server_tests/test_event_serialization.py",
        "test_all_events_serialize",
        S,
        "tests/manual/test_97_event_wire_contract.py::test_executed_event_lineages_round_trip_typed_values_through_json",
        "Bounded real movement and saving-throw lineages round-trip typed UUID, time, enum, tuple, and dice values through model JSON and the generated wire model without losing phase or lineage identity.",
    ),
    *(
        _row(
            "examples/server_tests/test_handler_toggle_api.py",
            case,
            S,
            "tests/engine/test_encounter_apis.py::test_eb_18_035_handler_toggle_round_trip_exposes_only_player_choices",
            "The session-bound round trip exposes only player-toggleable handlers and verifies persisted state.",
        )
        for case in (
            "test_get_handlers",
            "test_handler_details_in_actions",
            "test_toggle_handler",
            "test_toggle_persists_in_actions",
            "test_toggle_back_on",
            "test_toggle_non_toggleable_fails",
            "test_toggle_with_spaces",
        )
    ),
    _row(
        "examples/server_tests/test_jump_api.py",
        "test_jump_via_api",
        S,
        "tests/engine/test_manual_21_arena_game_sessions_client_state.py::test_jump_executes_through_canonical_action_and_replication_routes",
        "Jump now proves exact indexed execution, movement cost, replica state, trajectory, and log delivery.",
    ),
    _row(
        "examples/server_tests/test_server_api.py",
        "test_session_flow",
        S,
        "tests/manual/test_18_sessions_api_client_contract.py::test_session_create_join_ping_and_game_status",
        "Session creation, join, ping, ownership, and game status are asserted as one lifecycle.",
    ),
    _row(
        "examples/server_tests/test_server_api.py",
        "test_available_actions",
        S,
        "tests/manual/test_18_sessions_api_client_contract.py::test_subjective_state_and_available_actions_payloads",
        "Available actions are session-bound and compared with the subjective replica.",
    ),
    _row(
        "examples/server_tests/test_server_api.py",
        "test_self_action",
        S,
        "tests/engine/test_manual_21_arena_game_sessions_client_state.py::test_available_actions_action_results_and_log_cursors_drive_the_client_loop",
        "Dash executes through the sole indexed action endpoint and cursor-aligned journal.",
    ),
    _row(
        "examples/server_tests/test_server_api.py",
        "test_entity_action",
        S,
        "tests/manual/test_18_sessions_api_client_contract.py::test_execute_action_by_index_acknowledges_then_journals_state_and_logs",
        "Entity attacks use exact discovered rows and journal-owned damage/log state.",
    ),
    _row(
        "examples/server_tests/test_server_api.py",
        "test_position_action",
        S,
        "tests/manual/test_18_sessions_api_client_contract.py::test_execute_movement_delivers_typed_trajectory_through_replication",
        "Position actions use exact discovered rows and a typed presentation trajectory.",
    ),
    _row(
        "examples/server_tests/test_server_api.py",
        "test_execute_by_index",
        S,
        "tests/manual/test_18_sessions_api_client_contract.py::test_execute_action_by_index_acknowledges_then_journals_state_and_logs",
        "The retained indexed endpoint is validated end to end with exact cursors.",
    ),
    _row(
        "examples/server_tests/test_server_api.py",
        "test_end_turn",
        S,
        "tests/engine/test_encounter_apis.py::test_eb_18_037_turn_switch_updates_session_authority",
        "End-turn now proves HTTP success and the resulting derived session authority switch.",
    ),
    _row(
        "examples/server_tests/test_session_system.py",
        "test_player_session",
        S,
        "tests/manual/test_18_sessions_api_client_contract.py::test_player_session_activity_disconnect_and_ping_reconnect",
        "The direct maintained lifecycle proves exact last-activity advancement, disconnect state, and ping-driven reconnection.",
    ),
    _row(
        "examples/server_tests/test_session_system.py",
        "test_game_session",
        S,
        "tests/engine/test_encounter_apis.py::test_eb_18_033_game_join_status_and_session_entities_are_stateful",
        "GameSession ownership and active-player derivation are covered through joined sessions.",
    ),
    _row(
        "examples/server_tests/test_session_system.py",
        "test_session_manager",
        S,
        "tests/manual/test_18_sessions_api_client_contract.py::test_session_manager_reset_preserves_the_shared_registry",
        "The shared manager reset and registry identity are explicitly maintained.",
    ),
    _row(
        "examples/server_tests/test_session_system.py",
        "test_turn_validation",
        S,
        "tests/engine/test_encounter_apis.py::test_eb_18_026_session_authority_errors_report_action_context",
        "Turn denial is session-bound and returns typed authority correction context.",
    ),
    _row(
        "examples/server_tests/test_session_system.py",
        "test_turn_switching",
        S,
        "tests/engine/test_encounter_apis.py::test_eb_18_037_turn_switch_updates_session_authority",
        "Encounter advancement, status, ping, and action authorization now switch together.",
    ),

    # Subjective pathfinding, collision, and explicit targeting.
    _row(
        "examples/test_invisibility_pathfinding_leak.py",
        "test_invisible_does_not_block_subjective_paths",
        A,
        "tests/engine/test_senses_light_stealth.py::test_eb_12_007_subjective_paths_do_not_leak_imperceivable_blockers",
        "The direct subjective-path privacy invariant remains explicit.",
    ),
    _row(
        "examples/test_invisibility_pathfinding_leak.py",
        "test_truesight_blocked_by_invisible",
        A,
        "tests/engine/test_senses_light_stealth.py::test_eb_12_007_subjective_paths_do_not_leak_imperceivable_blockers",
        "The same regression proves truesight restores the blocker.",
    ),
    _row(
        "examples/test_invisibility_pathfinding_leak.py",
        "test_hidden_high_dc_not_blocking_low_perception",
        S,
        "tests/engine/test_senses_light_stealth.py::test_eb_12_032_hidden_transition_invalidates_subjective_occupancy_paths",
        "The maintained case now includes visible-to-Hidden cache invalidation.",
    ),
    _row(
        "examples/test_invisibility_pathfinding_leak.py",
        "test_hidden_blocks_high_perception_observer",
        S,
        "tests/engine/test_senses_light_stealth.py::test_eb_12_031_perception_thresholds_refilter_contacts_hazards_and_logs",
        "Perceived and unperceived hidden contacts are checked together across thresholds.",
    ),
    *(
        _row(
            "examples/test_invisibility_pathfinding_leak.py",
            case,
            S,
            "tests/engine/test_senses_light_stealth.py::test_eb_12_029_invisible_collision_stops_repaths_and_preserves_invisibility",
            "One deterministic movement transaction proves stop, event, memory, re-path, and preserved invisibility.",
        )
        for case in (
            "test_movement_stops_at_invisible_entity",
            "test_collision_fires_event",
            "test_collision_adds_to_collision_blocked",
            "test_repathing_avoids_collision_blocked",
        )
    ),
    _row(
        "examples/test_invisibility_pathfinding_leak.py",
        "test_collision_blocked_cleared_on_senses_update",
        T,
        "tests/engine/test_senses_light_stealth.py::test_eb_12_013_turn_start_clears_positional_and_directional_collision_memory",
        "Arbitrary senses recomputation no longer forgets learned collisions; the correct turn boundary clears them.",
    ),
    _row(
        "examples/test_invisibility_pathfinding_leak.py",
        "test_bump_hidden_destealths",
        A,
        "tests/engine/test_senses_light_stealth.py::test_eb_12_015_hidden_cell_blocker_reveals_on_movement_collision",
        "The direct hidden-collision reveal remains explicit.",
    ),
    _row(
        "examples/test_invisibility_pathfinding_leak.py",
        "test_bump_invisible_does_not_reveal",
        S,
        "tests/engine/test_senses_light_stealth.py::test_eb_12_029_invisible_collision_stops_repaths_and_preserves_invisibility",
        "The complete collision transaction explicitly preserves Invisible.",
    ),
    _row(
        "examples/test_invisibility_pathfinding_leak.py",
        "test_visible_entity_still_blocks",
        A,
        "tests/engine/test_senses_light_stealth.py::test_eb_12_007_subjective_paths_do_not_leak_imperceivable_blockers",
        "The visible/truesight control proves perceived occupancy still blocks.",
    ),
    _row(
        "examples/test_invisibility_pathfinding_leak.py",
        "test_paths_dirty_on_perceivability_change",
        S,
        "tests/engine/test_senses_light_stealth.py::test_eb_12_032_hidden_transition_invalidates_subjective_occupancy_paths",
        "The regression proves actual recomputation and both occupancy outcomes, not only a dirty flag.",
    ),
    *(
        _row(
            "examples/test_invisible_targeting.py",
            case,
            A,
            "tests/engine/test_senses_light_stealth.py::test_eb_12_030_multi_entity_spells_reject_unperceived_explicit_targets",
            "The parameterized maintained regression preserves this exact explicit-target variant and cost rollback.",
        )
        for case in (
            "test_mm_invisible_primary",
            "test_mm_invisible_extra",
            "test_bane_invisible",
            "test_bless_nonvisible_ally",
            "test_necrotic_bless_invisible",
            "test_mm_visible_targets",
        )
    ),

    # Perception threshold changes and their observable subjective/log effects.
    *(
        _row(
            "examples/test_perception_staleness.py",
            case,
            S,
            "tests/engine/test_senses_light_stealth.py::test_eb_12_031_perception_thresholds_refilter_contacts_hazards_and_logs",
            "One sequential threshold matrix proves entity, hazard, cache, and log behavior without manual refresh.",
        )
        for case in (
            "test_h1_wis_buff_reveals_hidden_enemy",
            "test_h2_wis_debuff_hides_previously_visible_enemy",
            "test_h3_varying_stealth_dc",
            "test_i1_wis_buff_reveals_hidden_trap",
            "test_i2_wis_debuff_hides_visible_trap",
            "test_i3_varying_trap_stealth_dc",
            "test_j1_entity_spotted_on_perception_buff",
            "test_j2_hazard_detected_on_perception_buff",
            "test_j3_no_false_positives",
            "test_k2_multiple_conditions_in_sequence",
        )
    ),
    _row(
        "examples/test_perception_staleness.py",
        "test_h4_truesight_reveals_invisible",
        A,
        "tests/engine/test_senses_light_stealth.py::test_eb_12_009_sense_mode_changes_emit_replacement_payloads",
        "Truesight replacement and the resulting visible entity are explicitly asserted.",
    ),
    _row(
        "examples/test_perception_staleness.py",
        "test_k1_snapshot_initialized_correctly",
        R,
        "tests/engine/test_senses_light_stealth.py::test_eb_12_012_passive_perception_changes_emit_replacement_payloads",
        "Private snapshot fields are retired as a test contract; their observable replacement payload is maintained.",
    ),
    _row(
        "examples/test_perception_staleness.py",
        "test_k3_condition_on_other_entity_no_self_recheck",
        S,
        "tests/engine/test_senses_light_stealth.py::test_eb_12_024_sensory_dispatch_targets_own_perception_conditions",
        "Candidate dispatch proves unrelated observers are excluded before recomputation.",
    ),
    _row(
        "examples/test_visibility_contract_payloads.py",
        "test_visibility_endpoint_includes_visible_objects",
        R,
        "tests/engine/test_manual_21_arena_game_sessions_client_state.py::test_player_replication_describes_the_subjective_live_arena",
        "The raw visibility endpoint was retired; the canonical player replica includes safe floor objects.",
    ),
    _row(
        "examples/test_visibility_contract_payloads.py",
        "test_sensory_update_includes_replacement_sense_modes",
        A,
        "tests/engine/test_senses_light_stealth.py::test_eb_12_009_sense_mode_changes_emit_replacement_payloads",
        "The typed grant payload and exact empty replacement after reactive removal are directly asserted.",
    ),
    _row(
        "examples/test_visibility_contract_payloads.py",
        "test_sensory_update_includes_replacement_passive_perception",
        A,
        "tests/engine/test_senses_light_stealth.py::test_eb_12_012_passive_perception_changes_emit_replacement_payloads",
        "The typed replacement passive-perception payload remains directly asserted.",
    ),

    # Three adjacent cases live outside D80's examples inventory.
    _row(
        "to_archive/tests/test_archived_cli_orchestration.py",
        "test_archived_codex_orchestrator_builds_guarded_codex_exec_invocation",
        R,
        "tests/manual/test_30_codex_takeover_tools.py::test_codex_cli_separates_takeover_transport_from_typed_hot_runtime_commands",
        "The old subprocess CLI prompt/orchestrator was retired in favor of typed takeover transport and runtime commands.",
    ),
    _row(
        "to_archive/tests/test_archived_cli_orchestration.py",
        "test_archived_codex_stream_metrics_track_current_item_events",
        R,
        "tests/manual/test_106_codex_session_transcript.py::test_transcript_retains_complete_subjective_lifecycle_with_digest_chain",
        "The old Codex JSONL CLI metric parser was retired; canonical transcripts retain the typed subjective lifecycle.",
    ),
    _row(
        "to_archive/tests/test_archived_cli_orchestration.py",
        "test_archived_combat_log_filter_reveals_only_parent_marked_aoe_targets",
        S,
        "tests/manual/test_113_subjective_combat_log_projection.py::test_every_entry_type_recursively_scrubs_an_unknown_identity",
        "The server projector now recursively censors typed logs using event-time evidence.",
    ),
)


D80_PATHS = {
    case.old_selector.split("::", 1)[0]
    for case in LEGACY_CASES
    if case.old_selector.startswith("examples/")
}


def test_manifest_accounts_for_exact_selected_d80_rows() -> None:
    """The 74 selected D80 rows and three adjacent CLI cases are exact."""
    with D80_MAP.open(newline="", encoding="utf-8") as handle:
        rows = csv.DictReader(handle, delimiter="\t")
        expected_d80 = {
            row["old_selector"]
            for row in rows
            if row["old_selector"].split("::", 1)[0] in D80_PATHS
        }

    manifest_selectors = {case.old_selector for case in LEGACY_CASES}
    manifest_d80 = {
        selector for selector in manifest_selectors if selector.startswith("examples/")
    }

    assert len(LEGACY_CASES) == 77
    assert len(manifest_selectors) == 77
    assert len(expected_d80) == 74
    assert manifest_d80 == expected_d80


def test_every_case_has_a_deliberate_disposition_and_explanation() -> None:
    """No selected case remains silently unmapped."""
    for case in LEGACY_CASES:
        assert case.disposition in CoverageDisposition
        assert case.replacements
        assert case.rationale.strip()


def test_every_replacement_selector_names_a_real_active_test() -> None:
    """Replacement links cannot drift to deleted or renamed tests."""
    parsed_files: dict[Path, set[str]] = {}
    for case in LEGACY_CASES:
        for replacement in case.replacements:
            relative_path, function_name = replacement.split("::", 1)
            path = ROOT / relative_path
            assert path.is_file(), replacement
            if path not in parsed_files:
                module = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
                parsed_files[path] = {
                    node.name
                    for node in module.body
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                }
            assert function_name in parsed_files[path], replacement
