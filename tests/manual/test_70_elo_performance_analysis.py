"""Retained-data performance analysis for the complete Elo evaluator."""

import json

from ai.evaluation.elo_contract import EloEligibility, EloMatchRecord
from ai.evaluation.elo_matrix import build_elo_matrix_schedule
from ai.evaluation.elo_performance import analyze_elo_performance
from ai.evaluation.tournament import TournamentMatchRecord


def test_performance_analysis_measures_turns_throughput_stages_and_arenas(tmp_path) -> None:
    """Raw traces drive every global and per-arena runtime measurement."""
    artifact_path = tmp_path / "run.json"
    artifact_path.write_text(json.dumps({
        "result": {
            "arena_id": "standard_skeleton_doors",
            "elapsed_ms": 1000.0,
            "command_count": 2,
            "final_round": 2,
            "traces": [
                _trace(round_number=1, turn_index=0, actor_uuid="hero"),
                _trace(round_number=1, turn_index=0, actor_uuid="hero"),
            ],
        }
    }), encoding="utf-8")
    schedule = build_elo_matrix_schedule(
        mode="elo_smoke",
        arena_ids=["standard_skeleton_doors"],
        seeds=[1],
        side_orders=(True,),
    )
    record = EloMatchRecord(
        match_id="performance-match",
        match_index=0,
        schedule_entry=schedule.entries[0],
        base_record=TournamentMatchRecord(
            match_id="performance-match",
            arena_id="standard_skeleton_doors",
            random_seed=1,
            hero_first=True,
            status="encounter_ended",
            command_count=2,
            elapsed_ms=1000.0,
            outcome="heroes",
            faction_hp={"heroes": 5, "monsters": 0},
            command_status_counts={"accepted": 2},
            subjectivity_status="passed",
            run_artifact_path=str(artifact_path),
        ),
        eligibility=EloEligibility(
            status="eligible",
            rating_eligible=True,
            subjectivity_status="passed",
            runner_status="encounter_ended",
            command_status_counts={"accepted": 2},
            encounter_finished=True,
            command_cap_reached=False,
            has_unknown_outcome=False,
        ),
        artifact_paths=[str(artifact_path)],
    )

    analysis = analyze_elo_performance(
        [record],
        evaluation_started_at="2026-01-01T00:00:00+00:00",
        evaluation_completed_at="2026-01-01T00:00:02+00:00",
    )
    arena = analysis.arenas[0]

    assert analysis.artifact_match_count == 1
    assert analysis.total_command_count == 2
    assert analysis.total_actor_turn_count == 1
    assert analysis.commands_per_second == 2.0
    assert analysis.actor_turns_per_second == 1.0
    assert analysis.evaluation_wall_elapsed_ms == 2000.0
    assert analysis.evaluator_overhead_ms == 1000.0
    assert analysis.simulation_time_share_pct == 50.0
    assert analysis.wall_matches_per_minute == 30.0
    assert analysis.wall_commands_per_second == 1.0
    assert analysis.wall_actor_turns_per_second == 0.5
    assert analysis.average_final_round == 2.0
    assert analysis.client_stage_ms["policy_ms"].mean == 2.0
    assert analysis.client_stage_share_pct["command_http_ms"] == 40.0
    assert analysis.diagnostic_components_ms["decision_epoch_build_ms"].mean == 3.0
    assert arena.match_count == 1
    assert arena.commands_per_match == 2.0
    assert arena.actor_turns_per_match == 1.0
    assert arena.side_order_counts == {"hero_first": 1}


def _trace(*, round_number: int, turn_index: int, actor_uuid: str) -> dict[str, object]:
    return {
        "round_number": round_number,
        "turn_index": turn_index,
        "actor_uuid": actor_uuid,
        "pre_command_sync_ms": 1.0,
        "fact_ms": 1.0,
        "policy_ms": 2.0,
        "command_http_ms": 4.0,
        "command_followup_sync_ms": 1.0,
        "total_ms": 10.0,
        "server_timing": {
            "total_ms": 6.0,
            "phases": {
                "publish.followup_epoch.build_decision_epoch_total_ms": 3.0,
                "publish.followup_epoch.get_available_actions_ms": 2.0,
                "publish.followup_epoch.build_affordance_set_ms": 1.0,
            },
        },
        "action_server_timing": {
            "total_ms": 2.0,
            "phases": {
                "execute_by_index_ms": 1.5,
                "execute_by_index.observation_projection.projection.project_events_ms": 0.5,
            },
        },
    }
