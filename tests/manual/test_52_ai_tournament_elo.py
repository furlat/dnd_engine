"""Tournament Elo summary tests."""

from ai.evaluation.tournament import (
    EloConfig,
    build_tournament_match_record,
    final_hp_by_faction,
    outcome_from_faction_hp,
    update_elo_pair,
)
from ai.external_selfplay import ExternalSelfPlayResult, ExternalSelfPlayTrace


def test_update_elo_pair_moves_winner_up_and_loser_down() -> None:
    """A decisive result should move ratings symmetrically from equality."""
    winner, loser = update_elo_pair(1000.0, 1000.0, 1.0, 0.0, k_factor=32.0)

    assert winner == 1016.0
    assert loser == 984.0


def test_outcome_from_faction_hp_handles_wins_draws_and_unknowns() -> None:
    """Final HP totals should produce compact tournament outcomes."""
    assert outcome_from_faction_hp({"heroes": 12, "monsters": 0}) == "heroes"
    assert outcome_from_faction_hp({"heroes": 0, "monsters": 8}) == "monsters"
    assert outcome_from_faction_hp({"heroes": 0, "monsters": 0}) == "draw"
    assert outcome_from_faction_hp({"heroes": 4, "monsters": 4}) == "draw"
    assert outcome_from_faction_hp({"heroes": 4}) == "unknown"


def test_build_tournament_match_record_rates_arena_sides() -> None:
    """A self-play result should become a structured setup-rating record."""
    result = ExternalSelfPlayResult(
        arena_id="srd_low_cr_patrol",
        status="encounter_ended",
        command_count=12,
        elapsed_ms=42.0,
        session_ids_by_faction={"heroes": "hero-session", "monsters": "monster-session"},
        final_round=2,
        final_state="ENDED",
        final_hp_by_actor={
            "Hero": 18,
            "Bandit": 0,
            "Guard": 0,
        },
        traces=[
            _trace(
                0,
                "Hero",
                "heroes",
                "accepted",
                total_ms=3.0,
                local_decision_ms=1.0,
                server_ms=1.4,
                deep_diagnostics=True,
                server_phases={"execute.action_by_index_ms": 0.9},
                action_phases={"execute_by_index.base_action.apply_total_ms": 0.7},
            ),
            _trace(
                1,
                "Bandit",
                "monsters",
                "stale",
                total_ms=5.0,
                local_decision_ms=2.0,
                server_ms=2.5,
                server_phases={"publish.followup_epoch.build_decision_epoch_total_ms": 1.8},
            ),
            _trace(2, "Guard", "monsters", "accepted", total_ms=4.0, local_decision_ms=1.5, server_ms=1.8),
        ],
    )

    record = build_tournament_match_record(
        result,
        match_id="match-1",
        random_seed=7,
        hero_first=True,
        ratings={},
        elo_config=EloConfig(),
    )

    assert final_hp_by_faction(result) == {"heroes": 18, "monsters": 0}
    assert record.outcome == "heroes"
    assert record.rating_after["srd_low_cr_patrol::heroes"] == 1016.0
    assert record.rating_after["srd_low_cr_patrol::monsters"] == 984.0
    assert record.rating_delta["srd_low_cr_patrol::heroes"] == 16.0
    assert record.command_status_counts == {"accepted": 2, "stale": 1}
    assert record.subjectivity_status == "passed"
    assert record.subjectivity_violation_count == 0
    assert record.max_command_total_ms == 5.0
    assert record.max_server_command_ms == 2.5
    assert record.max_local_decision_ms == 2.0
    assert record.command_total_samples_ms == [3.0, 5.0, 4.0]
    assert record.server_command_samples_ms == [1.4, 2.5, 1.8]
    assert record.local_decision_samples_ms == [1.0, 2.0, 1.5]
    assert record.normal_command_total_samples_ms == [5.0, 4.0]
    assert record.normal_server_command_samples_ms == [2.5, 1.8]
    assert record.normal_local_decision_samples_ms == [2.0, 1.5]
    assert record.diagnostic_command_total_samples_ms == [3.0]
    assert record.diagnostic_server_command_samples_ms == [1.4]
    assert record.diagnostic_local_decision_samples_ms == [1.0]
    assert record.stage_samples_ms["server.execute.action_by_index_ms"] == [0.9]
    assert record.stage_samples_ms["server.publish.followup_epoch.build_decision_epoch_total_ms"] == [1.8]
    assert record.stage_samples_ms["engine.execute_by_index.base_action.apply_total_ms"] == [0.7]
    assert record.normal_stage_samples_ms["server.publish.followup_epoch.build_decision_epoch_total_ms"] == [1.8]
    assert record.diagnostic_stage_samples_ms["server.execute.action_by_index_ms"] == [0.9]
    assert record.diagnostic_stage_samples_ms["engine.execute_by_index.base_action.apply_total_ms"] == [0.7]
    assert record.command_total_p95_ms == 5.0
    assert record.command_total_p99_ms == 5.0
    assert record.server_command_p95_ms == 2.5
    assert record.server_command_p99_ms == 2.5
    assert record.local_decision_p95_ms == 2.0
    assert record.local_decision_p99_ms == 2.0
    assert record.normal_command_total_p95_ms == 5.0
    assert record.normal_command_total_p99_ms == 5.0
    assert record.normal_server_command_p95_ms == 2.5
    assert record.normal_server_command_p99_ms == 2.5
    assert record.normal_local_decision_p95_ms == 2.0
    assert record.normal_local_decision_p99_ms == 2.0
    assert record.diagnostic_command_total_p95_ms == 3.0
    assert record.diagnostic_command_total_p99_ms == 3.0


def _trace(
    command_index: int,
    actor_name: str,
    actor_faction: str,
    status: str,
    *,
    total_ms: float,
    local_decision_ms: float,
    server_ms: float | None = None,
    deep_diagnostics: bool = False,
    server_phases: dict[str, float] | None = None,
    action_phases: dict[str, float] | None = None,
) -> ExternalSelfPlayTrace:
    server_timing: dict[str, object] = {"total_ms": server_ms} if server_ms is not None else {}
    if server_phases is not None:
        server_timing["phases"] = server_phases
    action_timing: dict[str, object] = {"phases": action_phases} if action_phases is not None else {}
    return ExternalSelfPlayTrace(
        command_index=command_index,
        round_number=1,
        turn_index=command_index,
        session_id=f"{actor_faction}-session",
        actor_uuid=f"{actor_faction}-{command_index}",
        actor_name=actor_name,
        actor_faction=actor_faction,
        entity_action_count=0,
        position_action_count=0,
        command_type="end_turn",
        reason="test",
        command_status=status,
        total_ms=total_ms,
        local_decision_ms=local_decision_ms,
        deep_diagnostics_enabled=deep_diagnostics,
        server_timing=server_timing,
        action_server_timing=action_timing,
        subjective_known_entity_uuids=[f"{actor_faction}-{command_index}"],
        subjective_known_entity_positions=[],
        subjective_known_tile_positions=[],
        audit_controlled_entity_uuids=[f"{actor_faction}-{command_index}"],
        audit_authorized_entity_uuids=[f"{actor_faction}-{command_index}"],
    )
