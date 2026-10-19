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
    replacement: str | None,
    rationale: str,
) -> LegacyCaseCoverage:
    """Build one exact manifest row."""
    return LegacyCaseCoverage(
        old_selector=f"{path}::{case}",
        disposition=disposition,
        replacements=(replacement,) if replacement is not None else (),
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
        "tests/ai/test_event_knowledge.py::test_brief_doorway_observation_is_remembered_between_decisions_and_replays",
        "TacticalState was retired; the replacement proves owned-observer identity, "
        "event-time observer visibility and typed remembered-entity facts "
        "without claiming the removed facade's helper fields.",
    ),
    _row(
        "examples/ai/test_ai_framework.py",
        "test_tactical_state_action_economy",
        R,
        None,
        'Retired TacticalState/behavior-tree framework consumer test_tactical_state_action_economy (historical source: agent_docs/to_archive/examples/ai/test_ai_framework.py). The old helper, trace, interrupt/goal and external-provider protocols are absent; current registered native policies are not an equivalent test of that removed mechanism.',
    ),
    _row(
        "examples/ai/test_ai_framework.py",
        "test_ev_computation",
        R,
        None,
        'Retired TacticalState/behavior-tree framework consumer test_ev_computation (historical source: agent_docs/to_archive/examples/ai/test_ai_framework.py). The old helper, trace, interrupt/goal and external-provider protocols are absent; current registered native policies are not an equivalent test of that removed mechanism.',
    ),
    _row(
        "examples/ai/test_ai_framework.py",
        "test_execute_action",
        R,
        None,
        'Retired TacticalState/behavior-tree framework consumer test_execute_action (historical source: agent_docs/to_archive/examples/ai/test_ai_framework.py). The old helper, trace, interrupt/goal and external-provider protocols are absent; current registered native policies are not an equivalent test of that removed mechanism.',
    ),
    _row(
        "examples/ai/test_ai_framework.py",
        "test_behavior_tree_agent",
        R,
        None,
        'Retired TacticalState/behavior-tree framework consumer test_behavior_tree_agent (historical source: agent_docs/to_archive/examples/ai/test_ai_framework.py). The old helper, trace, interrupt/goal and external-provider protocols are absent; current registered native policies are not an equivalent test of that removed mechanism.'
    ),
    _row(
        "examples/ai/test_ai_framework.py",
        "test_move_and_attack_composite",
        R,
        None,
        'Retired TacticalState/behavior-tree framework consumer test_move_and_attack_composite (historical source: agent_docs/to_archive/examples/ai/test_ai_framework.py). The old helper, trace, interrupt/goal and external-provider protocols are absent; current registered native policies are not an equivalent test of that removed mechanism.',
    ),
    _row(
        "examples/ai/test_ai_framework.py",
        "test_interrupt_detection",
        R,
        None,
        'Retired TacticalState/behavior-tree framework consumer test_interrupt_detection (historical source: agent_docs/to_archive/examples/ai/test_ai_framework.py). The old helper, trace, interrupt/goal and external-provider protocols are absent; current registered native policies are not an equivalent test of that removed mechanism.',
    ),
    _row(
        "examples/ai/test_ai_framework.py",
        "test_utility_scorer",
        R,
        None,
        'Retired TacticalState/behavior-tree framework consumer test_utility_scorer (historical source: agent_docs/to_archive/examples/ai/test_ai_framework.py). The old helper, trace, interrupt/goal and external-provider protocols are absent; current registered native policies are not an equivalent test of that removed mechanism.',
    ),
    _row(
        "examples/ai/test_ai_framework.py",
        "test_ai_controller_integration",
        R,
        None,
        'Retired TacticalState/behavior-tree framework consumer test_ai_controller_integration (historical source: agent_docs/to_archive/examples/ai/test_ai_framework.py). The old helper, trace, interrupt/goal and external-provider protocols are absent; current registered native policies are not an equivalent test of that removed mechanism.',
    ),
    _row(
        "examples/ai/test_ai_framework.py",
        "test_find_move_helpers",
        R,
        None,
        'Retired TacticalState/behavior-tree framework consumer test_find_move_helpers (historical source: agent_docs/to_archive/examples/ai/test_ai_framework.py). The old helper, trace, interrupt/goal and external-provider protocols are absent; current registered native policies are not an equivalent test of that removed mechanism.',
    ),

    # Successful canonical HTTP paths restored alongside the maintained errors.
    _row(
        "examples/server_tests/test_aoe_api.py",
        "test_aoe_via_api",
        R,
        None,
        'Retired threaded HTTP/session/replication consumer examples/server_tests/test_aoe_api.py; no compatibility claim for its former endpoints or DTOs. Disposition evidence: agent_docs/retired_server_tests/2026-09-21/README.md.',
    ),
    _row(
        "examples/server_tests/test_equipment_api.py",
        "test_get_equipment",
        R,
        None,
        'Retired threaded HTTP/session/replication consumer examples/server_tests/test_equipment_api.py; no compatibility claim for its former endpoints or DTOs. Disposition evidence: agent_docs/retired_server_tests/2026-09-21/README.md.',
    ),
    _row(
        "examples/server_tests/test_equipment_api.py",
        "test_get_item_detail",
        R,
        None,
        'Retired threaded HTTP/session/replication consumer examples/server_tests/test_equipment_api.py; no compatibility claim for its former endpoints or DTOs. Disposition evidence: agent_docs/retired_server_tests/2026-09-21/README.md.',
    ),
    _row(
        "examples/server_tests/test_equipment_api.py",
        "test_equippable_items",
        R,
        None,
        'Retired threaded HTTP/session/replication consumer examples/server_tests/test_equipment_api.py; no compatibility claim for its former endpoints or DTOs. Disposition evidence: agent_docs/retired_server_tests/2026-09-21/README.md.',
    ),
    _row(
        "examples/server_tests/test_equipment_api.py",
        "test_equip",
        R,
        None,
        'Retired threaded HTTP/session/replication consumer examples/server_tests/test_equipment_api.py; no compatibility claim for its former endpoints or DTOs. Disposition evidence: agent_docs/retired_server_tests/2026-09-21/README.md.',
    ),
    _row(
        "examples/server_tests/test_equipment_api.py",
        "test_unequip",
        R,
        None,
        'Retired threaded HTTP/session/replication consumer examples/server_tests/test_equipment_api.py; no compatibility claim for its former endpoints or DTOs. Disposition evidence: agent_docs/retired_server_tests/2026-09-21/README.md.',
    ),
    _row(
        "examples/server_tests/test_equipment_api.py",
        "test_errors",
        R,
        None,
        'Retired threaded HTTP/session/replication consumer examples/server_tests/test_equipment_api.py; no compatibility claim for its former endpoints or DTOs. Disposition evidence: agent_docs/retired_server_tests/2026-09-21/README.md.',
    ),
    _row(
        "examples/server_tests/test_equipment_api.py",
        "test_entity_full",
        R,
        None,
        'Retired threaded HTTP/session/replication consumer examples/server_tests/test_equipment_api.py; no compatibility claim for its former endpoints or DTOs. Disposition evidence: agent_docs/retired_server_tests/2026-09-21/README.md.',
    ),
    _row(
        "examples/server_tests/test_event_serialization.py",
        "test_all_events_serialize",
        R,
        None,
        'Retired threaded HTTP/session/replication consumer examples/server_tests/test_event_serialization.py; no compatibility claim for its former endpoints or DTOs. Disposition evidence: agent_docs/retired_server_tests/2026-09-21/README.md.',
    ),
    *(
        _row(
            "examples/server_tests/test_handler_toggle_api.py",
            case,
            R,
            None,
            'Retired threaded HTTP/session/replication consumer examples/server_tests/test_handler_toggle_api.py; no compatibility claim for its former endpoints or DTOs. Disposition evidence: agent_docs/retired_server_tests/2026-09-21/README.md.',
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
        R,
        None,
        'Retired threaded HTTP/session/replication consumer examples/server_tests/test_jump_api.py; no compatibility claim for its former endpoints or DTOs. Disposition evidence: agent_docs/retired_server_tests/2026-09-21/README.md.',
    ),
    _row(
        "examples/server_tests/test_server_api.py",
        "test_session_flow",
        R,
        None,
        'Retired threaded HTTP/session/replication consumer examples/server_tests/test_server_api.py; no compatibility claim for its former endpoints or DTOs. Disposition evidence: agent_docs/retired_server_tests/2026-09-21/README.md.',
    ),
    _row(
        "examples/server_tests/test_server_api.py",
        "test_available_actions",
        R,
        None,
        'Retired threaded HTTP/session/replication consumer examples/server_tests/test_server_api.py; no compatibility claim for its former endpoints or DTOs. Disposition evidence: agent_docs/retired_server_tests/2026-09-21/README.md.',
    ),
    _row(
        "examples/server_tests/test_server_api.py",
        "test_self_action",
        R,
        None,
        'Retired threaded HTTP/session/replication consumer examples/server_tests/test_server_api.py; no compatibility claim for its former endpoints or DTOs. Disposition evidence: agent_docs/retired_server_tests/2026-09-21/README.md.',
    ),
    _row(
        "examples/server_tests/test_server_api.py",
        "test_entity_action",
        R,
        None,
        'Retired threaded HTTP/session/replication consumer examples/server_tests/test_server_api.py; no compatibility claim for its former endpoints or DTOs. Disposition evidence: agent_docs/retired_server_tests/2026-09-21/README.md.',
    ),
    _row(
        "examples/server_tests/test_server_api.py",
        "test_position_action",
        R,
        None,
        'Retired threaded HTTP/session/replication consumer examples/server_tests/test_server_api.py; no compatibility claim for its former endpoints or DTOs. Disposition evidence: agent_docs/retired_server_tests/2026-09-21/README.md.',
    ),
    _row(
        "examples/server_tests/test_server_api.py",
        "test_execute_by_index",
        R,
        None,
        'Retired threaded HTTP/session/replication consumer examples/server_tests/test_server_api.py; no compatibility claim for its former endpoints or DTOs. Disposition evidence: agent_docs/retired_server_tests/2026-09-21/README.md.',
    ),
    _row(
        "examples/server_tests/test_server_api.py",
        "test_end_turn",
        R,
        None,
        'Retired threaded HTTP/session/replication consumer examples/server_tests/test_server_api.py; no compatibility claim for its former endpoints or DTOs. Disposition evidence: agent_docs/retired_server_tests/2026-09-21/README.md.',
    ),
    _row(
        "examples/server_tests/test_session_system.py",
        "test_player_session",
        R,
        None,
        'Retired threaded HTTP/session/replication consumer examples/server_tests/test_session_system.py; no compatibility claim for its former endpoints or DTOs. Disposition evidence: agent_docs/retired_server_tests/2026-09-21/README.md.',
    ),
    _row(
        "examples/server_tests/test_session_system.py",
        "test_game_session",
        R,
        None,
        'Retired threaded HTTP/session/replication consumer examples/server_tests/test_session_system.py; no compatibility claim for its former endpoints or DTOs. Disposition evidence: agent_docs/retired_server_tests/2026-09-21/README.md.',
    ),
    _row(
        "examples/server_tests/test_session_system.py",
        "test_session_manager",
        R,
        None,
        'Retired threaded HTTP/session/replication consumer examples/server_tests/test_session_system.py; no compatibility claim for its former endpoints or DTOs. Disposition evidence: agent_docs/retired_server_tests/2026-09-21/README.md.',
    ),
    _row(
        "examples/server_tests/test_session_system.py",
        "test_turn_validation",
        R,
        None,
        'Retired threaded HTTP/session/replication consumer examples/server_tests/test_session_system.py; no compatibility claim for its former endpoints or DTOs. Disposition evidence: agent_docs/retired_server_tests/2026-09-21/README.md.',
    ),
    _row(
        "examples/server_tests/test_session_system.py",
        "test_turn_switching",
        R,
        None,
        'Retired threaded HTTP/session/replication consumer examples/server_tests/test_session_system.py; no compatibility claim for its former endpoints or DTOs. Disposition evidence: agent_docs/retired_server_tests/2026-09-21/README.md.',
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
        'tests/engine/test_senses_light_stealth.py::test_eb_12_031_perception_thresholds_refilter_contacts_and_hazards',
        'Sequential native perception thresholds refilter entity contacts, traps, hazards and subjective routes without manual refresh; this successor makes no combat-log assertion.',
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
            'tests/engine/test_senses_light_stealth.py::test_eb_12_031_perception_thresholds_refilter_contacts_and_hazards',
            'Sequential native perception thresholds refilter entity contacts, traps, hazards and subjective routes without manual refresh; this successor makes no combat-log assertion.',
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
        None,
        'Retired threaded HTTP/session/replication consumer examples/test_visibility_contract_payloads.py; no compatibility claim for its former endpoints or DTOs. Disposition evidence: agent_docs/retired_server_tests/2026-09-21/README.md.',
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
        None,
        'Retired Codex subprocess CLI orchestration/JSONL metric consumer; no active CLI invocation or parser implementation remains. Native AI command/knowledge tests do not claim compatibility with that removed transport.',
    ),
    _row(
        "to_archive/tests/test_archived_cli_orchestration.py",
        "test_archived_codex_stream_metrics_track_current_item_events",
        R,
        None,
        'Retired Codex subprocess CLI orchestration/JSONL metric consumer; no active CLI invocation or parser implementation remains. Native AI command/knowledge tests do not claim compatibility with that removed transport.',
    ),
    _row(
        "to_archive/tests/test_archived_cli_orchestration.py",
        "test_archived_combat_log_filter_reveals_only_parent_marked_aoe_targets",
        R,
        'tests/engine/test_subjective_combat_log_replay.py::test_visible_child_retains_its_sanitized_hidden_parent',
        'The CLI parent-marked reveal filter was retired. Native event-time projection instead retains a visible child while sanitizing its unknown parent; this is a privacy successor, not compatibility with the old global AoE reveal grant.',
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
        assert case.replacements or case.disposition is CoverageDisposition.RETIRED
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
