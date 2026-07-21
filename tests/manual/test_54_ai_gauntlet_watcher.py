"""Gauntlet schedule, summary, and watcher contract tests."""

import pytest

from ai.evaluation.gauntlet import (
    GauntletEventStream,
    build_gauntlet_schedule,
    build_gauntlet_summary,
    build_regression_schedule,
    project_watcher_state,
    validate_gauntlet_summary_evidence,
)
from ai.evaluation.tournament import EloConfig, TournamentMatchRecord, TournamentSummary
from dnd.scenarios.ai_validation_arenas import list_ai_validation_arena_specs


def test_build_gauntlet_schedule_modes_are_typed_and_repeatable() -> None:
    """Named gauntlet modes should produce tagged deterministic schedule rows."""
    schedule = build_gauntlet_schedule(
        "rotation",
        arena_ids=["standard_skeleton_doors"],
        seeds=[11, 12, 13, 14, 15, 16],
        policy_version="policy-test",
    )

    assert schedule.mode == "rotation"
    assert len(schedule.entries) == 6
    assert schedule.schedule_hash
    assert [entry.match_index for entry in schedule.entries] == list(range(6))
    assert {entry.hero_profile for entry in schedule.entries} >= {
        "codex_barbarian",
        "codex_sorcerer",
        "ai_barbarian",
        "ai_sorcerer",
    }
    assert {entry.monster_profile for entry in schedule.entries} >= {"ai_monsters", "codex_skeletons"}
    assert all(entry.policy_version == "policy-test" for entry in schedule.entries)


def test_default_gauntlet_modes_use_registered_validation_arenas() -> None:
    """Default schedules should never reference missing validation arenas."""
    known_arena_ids = {spec.arena_id for spec in list_ai_validation_arena_specs()}

    for mode in ("smoke", "rotation", "content", "release"):
        schedule = build_gauntlet_schedule(mode)
        assert schedule.entries
        assert {entry.arena_id for entry in schedule.entries} <= known_arena_ids


def test_default_rotation_schedule_is_the_required_six_game_rotation() -> None:
    """The rotation mode should encode exactly the six named validation slots."""
    schedule = build_gauntlet_schedule("rotation")

    assert len(schedule.entries) == 6
    assert [entry.match_index for entry in schedule.entries] == list(range(6))
    assert [entry.random_seed for entry in schedule.entries] == [1, 2, 3, 4, 5, 6]
    assert [(entry.hero_profile, entry.monster_profile) for entry in schedule.entries] == [
        ("codex_barbarian", "ai_monsters"),
        ("codex_sorcerer", "ai_monsters"),
        ("ai_barbarian", "codex_skeletons"),
        ("ai_sorcerer", "codex_skeletons"),
        ("ai_barbarian", "ai_monsters"),
        ("ai_sorcerer", "ai_monsters"),
    ]
    assert all(entry.arena_id == "standard_skeleton_doors" for entry in schedule.entries)
    assert all("rotation" in entry.tags for entry in schedule.entries)


def test_gauntlet_schedule_rejects_unknown_arena_override() -> None:
    """Explicit arena overrides should fail before a gauntlet can emit false evidence."""
    with pytest.raises(ValueError, match="missing_arena"):
        build_gauntlet_schedule("smoke", arena_ids=["standard_skeleton_doors", "missing_arena"], seeds=[1])


def test_gauntlet_summary_keeps_failures_visible_and_pending_counted() -> None:
    """Abnormal matches should remain visible rather than disappearing into ratings."""
    schedule = build_gauntlet_schedule("smoke", arena_ids=["standard_skeleton_doors"], seeds=[1, 2])
    tournament = TournamentSummary(
        tournament_id="tournament-test",
        generated_at="2026-07-16T00:00:00+00:00",
        elo_config=EloConfig(),
        arena_ids=["standard_skeleton_doors"],
        matches=[
            TournamentMatchRecord(
                match_id="match-ok",
                arena_id="standard_skeleton_doors",
                random_seed=1,
                hero_first=True,
                status="encounter_ended",
                command_count=10,
                elapsed_ms=15.0,
                outcome="heroes",
                faction_hp={"heroes": 12, "monsters": 0},
                command_status_counts={"accepted": 10},
                subjectivity_status="passed",
                subjectivity_violation_count=0,
                max_command_total_ms=4.0,
                max_server_command_ms=2.0,
                max_local_decision_ms=1.0,
                run_artifact_path="runs/match-ok.json",
            ),
            TournamentMatchRecord(
                match_id="match-leak",
                arena_id="standard_skeleton_doors",
                random_seed=2,
                hero_first=False,
                status="subjectivity_leak",
                command_count=4,
                elapsed_ms=8.0,
                outcome="unknown",
                faction_hp={},
                command_status_counts={"accepted": 2, "stale": 1, "rejected": 1},
                subjectivity_status="failed",
                subjectivity_violation_count=2,
                max_command_total_ms=9.0,
                max_server_command_ms=7.0,
                max_local_decision_ms=3.0,
                run_artifact_path="runs/match-leak.json",
            ),
        ],
    )

    summary = build_gauntlet_summary(schedule, tournament)

    assert summary.completed_count == 1
    assert summary.failed_count == 1
    assert summary.pending_count == 0
    assert summary.failed_match_ids == ["match-leak"]
    assert summary.subjectivity_violation_match_ids == ["match-leak"]
    assert [match.match_id for match in summary.matches] == ["match-ok", "match-leak"]
    assert summary.status_counts == {"encounter_ended": 1, "subjectivity_leak": 1}
    assert summary.outcome_counts == {"heroes": 1, "unknown": 1}
    assert summary.command_status_counts == {"accepted": 12, "rejected": 1, "stale": 1}
    assert summary.performance is not None
    assert summary.performance.match_count == 2
    assert summary.performance.total_command_count == 14
    assert summary.performance.average_command_count == 7.0
    assert summary.performance.total_elapsed_ms == 23.0
    assert summary.performance.max_command_total_ms == 9.0
    assert summary.performance.max_server_command_ms == 7.0
    assert summary.performance.max_local_decision_ms == 3.0
    assert summary.performance.command_total_sample_count == 0
    assert summary.performance.normal_command_total_sample_count == 0
    assert summary.performance.diagnostic_command_total_sample_count == 0
    assert summary.performance.command_total_p95_ms is None
    assert summary.performance.command_total_p99_ms is None
    assert summary.artifact_paths == ["runs/match-ok.json", "runs/match-leak.json"]
    assert summary.subjectivity_status == "failed"
    assert summary.subjectivity_violation_count == 2
    assert summary.gate_status == "failed"
    assert summary.gate_reasons == ["failed_matches", "subjectivity_violations", "stale_commands"]
    assert summary.latency_status == "passed"
    assert summary.latency_reasons == []
    assert len(summary.failure_rows) == 1
    assert summary.failure_rows[0].match_id == "match-leak"
    assert summary.failure_rows[0].run_artifact_path == "runs/match-leak.json"


def test_gauntlet_summary_treats_stale_completed_matches_as_failures() -> None:
    """A completed encounter with stale command evidence is not release-clean."""
    schedule = build_gauntlet_schedule("smoke", arena_ids=["standard_skeleton_doors"], seeds=[1])
    tournament = TournamentSummary(
        tournament_id=schedule.gauntlet_id,
        generated_at="2026-07-16T00:00:00+00:00",
        elo_config=EloConfig(),
        arena_ids=["standard_skeleton_doors"],
        matches=[
            TournamentMatchRecord(
                match_id=f"{schedule.gauntlet_id}-0000",
                arena_id="standard_skeleton_doors",
                random_seed=1,
                hero_first=True,
                status="encounter_ended",
                command_count=8,
                elapsed_ms=12.0,
                outcome="heroes",
                faction_hp={"heroes": 9, "monsters": 0},
                command_status_counts={"accepted": 7, "stale": 1},
                subjectivity_status="passed",
            )
        ],
    )

    summary = build_gauntlet_summary(schedule, tournament)

    assert summary.completed_count == 0
    assert summary.failed_count == 1
    assert summary.failed_match_ids == [f"{schedule.gauntlet_id}-0000"]
    assert len(summary.failure_rows) == 1
    assert summary.failure_rows[0].reason == "stale_command"
    assert summary.command_status_counts == {"accepted": 7, "stale": 1}
    assert summary.gate_status == "failed"
    assert summary.gate_reasons == ["failed_matches", "stale_commands"]


def test_gauntlet_summary_marks_partial_clean_batch_as_running() -> None:
    """A clean partial schedule is observable but not release-passing."""
    schedule = build_gauntlet_schedule("smoke", arena_ids=["standard_skeleton_doors"], seeds=[1, 2])
    tournament = TournamentSummary(
        tournament_id=schedule.gauntlet_id,
        generated_at="2026-07-16T00:00:00+00:00",
        elo_config=EloConfig(),
        arena_ids=["standard_skeleton_doors"],
        matches=[
            TournamentMatchRecord(
                match_id=f"{schedule.gauntlet_id}-0000",
                arena_id="standard_skeleton_doors",
                random_seed=1,
                hero_first=True,
                status="encounter_ended",
                command_count=4,
                elapsed_ms=8.0,
                outcome="heroes",
                command_status_counts={"accepted": 4},
                subjectivity_status="passed",
            )
        ],
    )

    summary = build_gauntlet_summary(schedule, tournament)

    assert summary.completed_count == 1
    assert summary.pending_count == 1
    assert summary.failed_count == 0
    assert summary.gate_status == "running"
    assert summary.gate_reasons == ["pending_matches"]


def test_gauntlet_summary_latency_audit_distinguishes_fast_slow_and_missing() -> None:
    """Latency audit should be explicit rather than folded into release-clean status."""
    fast = _latency_summary(max_command_total_ms=4.0, max_local_decision_ms=4.0)
    slow = _latency_summary(max_command_total_ms=12.0, max_local_decision_ms=6.0)
    missing = _latency_summary(max_command_total_ms=None, max_local_decision_ms=None)

    assert fast.gate_status == "passed"
    assert fast.latency_status == "passed"
    assert fast.latency_reasons == []
    assert slow.gate_status == "passed"
    assert slow.latency_status == "failed"
    assert slow.latency_reasons == [
        "command_total_p95_over_5ms",
        "command_total_p99_over_10ms",
        "local_decision_p99_over_5ms",
    ]
    assert missing.gate_status == "passed"
    assert missing.latency_status == "failed"
    assert missing.latency_reasons == ["missing_command_total_latency", "missing_local_decision_latency"]


def test_gauntlet_latency_audit_uses_normal_samples_before_diagnostic_samples() -> None:
    """Probe-heavy diagnostics should stay visible without failing production latency."""
    schedule = build_gauntlet_schedule("smoke", arena_ids=["standard_skeleton_doors"], seeds=[1])
    tournament = TournamentSummary(
        tournament_id=schedule.gauntlet_id,
        generated_at="2026-07-16T00:00:00+00:00",
        elo_config=EloConfig(),
        arena_ids=["standard_skeleton_doors"],
        matches=[
            TournamentMatchRecord(
                match_id=f"{schedule.gauntlet_id}-0000",
                arena_id="standard_skeleton_doors",
                random_seed=1,
                hero_first=True,
                status="encounter_ended",
                command_count=2,
                elapsed_ms=8.0,
                outcome="heroes",
                command_status_counts={"accepted": 2},
                subjectivity_status="passed",
                max_command_total_ms=80.0,
                max_server_command_ms=70.0,
                max_local_decision_ms=4.0,
                command_total_samples_ms=[4.0, 80.0],
                server_command_samples_ms=[2.0, 70.0],
                local_decision_samples_ms=[2.0, 4.0],
                normal_command_total_samples_ms=[4.0],
                normal_server_command_samples_ms=[2.0],
                normal_local_decision_samples_ms=[2.0],
                diagnostic_command_total_samples_ms=[80.0],
                diagnostic_server_command_samples_ms=[70.0],
                diagnostic_local_decision_samples_ms=[4.0],
                stage_samples_ms={
                    "command_http_ms": [3.0, 60.0],
                    "local_decision_ms": [2.0, 4.0],
                    "server.publish.followup_epoch.build_decision_epoch_total_ms": [9.0, 40.0],
                    "engine.execute_by_index.base_action.apply_total_ms": [12.0],
                },
                normal_stage_samples_ms={
                    "command_http_ms": [3.0],
                    "local_decision_ms": [2.0],
                    "server.publish.followup_epoch.build_decision_epoch_total_ms": [9.0],
                },
                diagnostic_stage_samples_ms={
                    "command_http_ms": [60.0],
                    "local_decision_ms": [4.0],
                    "server.publish.followup_epoch.build_decision_epoch_total_ms": [40.0],
                    "engine.execute_by_index.base_action.apply_total_ms": [12.0],
                },
                command_total_p95_ms=80.0,
                command_total_p99_ms=80.0,
                server_command_p95_ms=70.0,
                server_command_p99_ms=70.0,
                local_decision_p95_ms=4.0,
                local_decision_p99_ms=4.0,
                normal_command_total_p95_ms=4.0,
                normal_command_total_p99_ms=4.0,
                normal_server_command_p95_ms=2.0,
                normal_server_command_p99_ms=2.0,
                normal_local_decision_p95_ms=2.0,
                normal_local_decision_p99_ms=2.0,
                diagnostic_command_total_p95_ms=80.0,
                diagnostic_command_total_p99_ms=80.0,
                diagnostic_server_command_p95_ms=70.0,
                diagnostic_server_command_p99_ms=70.0,
                diagnostic_local_decision_p95_ms=4.0,
                diagnostic_local_decision_p99_ms=4.0,
            )
        ],
    )

    summary = build_gauntlet_summary(schedule, tournament)

    assert summary.latency_status == "passed"
    assert summary.latency_reasons == []
    assert summary.performance is not None
    assert summary.performance.command_total_p99_ms == 80.0
    assert summary.performance.normal_command_total_p99_ms == 4.0
    assert summary.performance.diagnostic_command_total_p99_ms == 80.0
    assert summary.performance.max_diagnostic_server_command_ms == 70.0
    assert summary.performance.stages["command_http_ms"].sample_count == 2
    assert summary.performance.stages["command_http_ms"].p95_ms == 60.0
    assert summary.performance.normal_stages["command_http_ms"].max_ms == 3.0
    assert summary.performance.diagnostic_stages["local_decision_ms"].max_ms == 4.0
    assert summary.performance.stages["server.publish.followup_epoch.build_decision_epoch_total_ms"].max_ms == 40.0
    assert summary.performance.normal_stages["server.publish.followup_epoch.build_decision_epoch_total_ms"].max_ms == 9.0
    assert summary.performance.diagnostic_stages["engine.execute_by_index.base_action.apply_total_ms"].max_ms == 12.0


def test_gauntlet_summary_evidence_validator_accepts_builder_output() -> None:
    """Builder-produced summaries should satisfy the retained evidence contract."""
    schedule = build_gauntlet_schedule("smoke", arena_ids=["standard_skeleton_doors"], seeds=[1])
    tournament = TournamentSummary(
        tournament_id=schedule.gauntlet_id,
        generated_at="2026-07-16T00:00:00+00:00",
        elo_config=EloConfig(),
        arena_ids=["standard_skeleton_doors"],
        matches=[
            TournamentMatchRecord(
                match_id=f"{schedule.gauntlet_id}-0000",
                arena_id="standard_skeleton_doors",
                random_seed=1,
                hero_first=True,
                status="encounter_ended",
                command_count=4,
                elapsed_ms=8.0,
                outcome="heroes",
                command_status_counts={"accepted": 4},
                subjectivity_status="passed",
            )
        ],
    )
    stream = GauntletEventStream()
    stream.append(event_type="GAUNTLET_STARTED", gauntlet_id=schedule.gauntlet_id, status="running")
    stream.append(
        event_type="MATCH_COMPLETED",
        gauntlet_id=schedule.gauntlet_id,
        match_id=f"{schedule.gauntlet_id}-0000",
        match_index=0,
        status="encounter_ended",
    )
    summary = build_gauntlet_summary(schedule, tournament, stream.since(0))

    assert validate_gauntlet_summary_evidence(summary) is summary
    assert project_watcher_state(summary).gate_status == "passed"


def test_gauntlet_summary_evidence_validator_rejects_false_clean_counts() -> None:
    """Count fields should not be allowed to contradict retained match rows."""
    summary = _stale_gauntlet_summary()
    bad = summary.model_copy(update={"completed_count": 1, "failed_count": 0})

    with pytest.raises(ValueError, match="failed count"):
        validate_gauntlet_summary_evidence(bad)


def test_gauntlet_summary_evidence_validator_rejects_missing_failure_rows() -> None:
    """Abnormal matches must stay visible in failure rows."""
    summary = _stale_gauntlet_summary()
    bad = summary.model_copy(update={"failure_rows": []})

    with pytest.raises(ValueError, match="failure rows"):
        validate_gauntlet_summary_evidence(bad)


def test_gauntlet_summary_evidence_validator_rejects_command_total_lies() -> None:
    """Aggregated command status counts should be derived from retained matches."""
    summary = _stale_gauntlet_summary()
    bad = summary.model_copy(update={"command_status_counts": {"accepted": 8}})

    with pytest.raises(ValueError, match="command status counts"):
        validate_gauntlet_summary_evidence(bad)


def test_gauntlet_summary_evidence_validator_rejects_bad_event_cursors() -> None:
    """Watcher event history must remain cursor-ordered and replayable."""
    summary = _stale_gauntlet_summary()
    bad = summary.model_copy(update={"events": [summary.events[1], summary.events[0]]})

    with pytest.raises(ValueError, match="unique and ordered"):
        validate_gauntlet_summary_evidence(bad)


def test_regression_schedule_replays_retained_failed_rows() -> None:
    """Failed retained rows should become a normal replayable regression schedule."""
    schedule = build_gauntlet_schedule(
        "rotation",
        arena_ids=["standard_skeleton_doors"],
        seeds=[11, 12],
        policy_version="old-policy",
    )
    tournament = TournamentSummary(
        tournament_id=schedule.gauntlet_id,
        generated_at="2026-07-16T00:00:00+00:00",
        elo_config=EloConfig(),
        arena_ids=["standard_skeleton_doors"],
        matches=[
            TournamentMatchRecord(
                match_id=f"{schedule.gauntlet_id}-0000",
                arena_id="standard_skeleton_doors",
                random_seed=11,
                hero_first=True,
                status="encounter_ended",
                command_count=2,
                elapsed_ms=5.0,
                outcome="heroes",
            ),
            TournamentMatchRecord(
                match_id=f"{schedule.gauntlet_id}-0001",
                arena_id="standard_skeleton_doors",
                random_seed=12,
                hero_first=False,
                status="timeout",
                command_count=80,
                elapsed_ms=500.0,
                outcome="unknown",
            ),
        ],
    )
    summary = build_gauntlet_summary(schedule, tournament)

    regression = build_regression_schedule(summary, policy_version="new-policy")

    assert regression.mode == "regression"
    assert len(regression.entries) == 1
    replay = regression.entries[0]
    assert replay.match_index == 0
    assert replay.arena_id == "standard_skeleton_doors"
    assert replay.random_seed == 12
    assert replay.hero_first is False
    assert replay.policy_version == "new-policy"
    assert "regression" in replay.tags
    assert "replay" in replay.tags
    assert "status:timeout" in replay.tags


def test_regression_schedule_rejects_missing_source_arena() -> None:
    """Regression replay should fail fast if retained evidence references an obsolete arena."""
    schedule = build_gauntlet_schedule("smoke", arena_ids=["standard_skeleton_doors"], seeds=[1])
    bad_schedule = schedule.model_copy(
        update={
            "entries": [
                schedule.entries[0].model_copy(update={"arena_id": "renamed_or_deleted_arena"})
            ]
        }
    )
    tournament = TournamentSummary(
        tournament_id=bad_schedule.gauntlet_id,
        generated_at="2026-07-16T00:00:00+00:00",
        elo_config=EloConfig(),
        arena_ids=["renamed_or_deleted_arena"],
        matches=[
            TournamentMatchRecord(
                match_id=f"{bad_schedule.gauntlet_id}-0000",
                arena_id="renamed_or_deleted_arena",
                random_seed=1,
                hero_first=True,
                status="timeout",
                command_count=80,
                elapsed_ms=500.0,
                outcome="unknown",
            )
        ],
    )
    summary = build_gauntlet_summary(bad_schedule, tournament)

    with pytest.raises(ValueError, match="renamed_or_deleted_arena"):
        build_regression_schedule(summary)


def test_gauntlet_event_stream_replays_by_cursor() -> None:
    """Watcher event streams should be monotonic and replayable from a cursor."""
    stream = GauntletEventStream(max_events=8)
    first = stream.append(event_type="GAUNTLET_STARTED", gauntlet_id="g1", status="running")
    second = stream.append(event_type="MATCH_STARTED", gauntlet_id="g1", match_id="m1", match_index=0)
    third = stream.append(event_type="MATCH_PROGRESS", gauntlet_id="g1", match_id="m1", status="encounter_ended")
    fourth = stream.append(event_type="RATING_UPDATED", gauntlet_id="g1", match_id="m1", status="ratings_updated")
    fifth = stream.append(event_type="MATCH_COMPLETED", gauntlet_id="g1", match_id="m1", status="encounter_ended")

    assert first.cursor == 1
    assert second.cursor == 2
    assert third.cursor == 3
    assert fourth.cursor == 4
    assert fifth.cursor == 5
    assert [event.cursor for event in stream.since(1)] == [2, 3, 4, 5]
    assert [event.event_type for event in stream.since(2)] == ["MATCH_PROGRESS", "RATING_UPDATED", "MATCH_COMPLETED"]


def test_watcher_projection_reports_active_match_and_terminal_summary() -> None:
    """Watcher state should combine compact summary and live events."""
    schedule = build_gauntlet_schedule("smoke", arena_ids=["standard_skeleton_doors"], seeds=[1])
    tournament = TournamentSummary(
        tournament_id="tournament-test",
        generated_at="2026-07-16T00:00:00+00:00",
        elo_config=EloConfig(),
        arena_ids=["standard_skeleton_doors"],
        matches=[],
    )
    stream = GauntletEventStream()
    stream.append(event_type="GAUNTLET_STARTED", gauntlet_id=schedule.gauntlet_id, status="running")
    stream.append(event_type="MATCH_STARTED", gauntlet_id=schedule.gauntlet_id, match_id="m1", match_index=0)
    summary = build_gauntlet_summary(schedule, tournament, stream.since(0))

    active_state = project_watcher_state(summary)

    assert active_state.status == "running"
    assert active_state.active_match_id == "m1"
    assert active_state.pending_count == 1

    completed_tournament = tournament.model_copy(
        update={
            "matches": [
                TournamentMatchRecord(
                    match_id="m1",
                    arena_id="standard_skeleton_doors",
                    random_seed=1,
                    hero_first=True,
                    status="encounter_ended",
                    command_count=7,
                    elapsed_ms=20.0,
                    outcome="monsters",
                    faction_hp={"heroes": 0, "monsters": 3},
                    command_status_counts={"accepted": 7},
                    subjectivity_status="passed",
                    subjectivity_violation_count=0,
                    max_command_total_ms=5.0,
                    max_server_command_ms=3.0,
                    max_local_decision_ms=2.0,
                )
            ]
        }
    )
    stream.append(event_type="MATCH_COMPLETED", gauntlet_id=schedule.gauntlet_id, match_id="m1", status="encounter_ended")
    stream.append(event_type="GAUNTLET_COMPLETED", gauntlet_id=schedule.gauntlet_id, status="completed")
    completed_summary = build_gauntlet_summary(schedule, completed_tournament, stream.since(0))

    terminal_state = project_watcher_state(completed_summary)

    assert terminal_state.status == "completed"
    assert terminal_state.active_match_id is None
    assert terminal_state.latest_outcome == "monsters"
    assert terminal_state.completed_count == 1
    assert terminal_state.performance is not None
    assert terminal_state.performance.total_command_count == 7
    assert terminal_state.performance.max_command_total_ms == 5.0
    assert terminal_state.performance.max_server_command_ms == 3.0
    assert terminal_state.performance.command_total_p95_ms is None
    assert terminal_state.performance.command_total_p99_ms is None
    assert terminal_state.command_status_counts == {"accepted": 7}
    assert terminal_state.outcome_counts == {"monsters": 1}
    assert terminal_state.subjectivity_status == "passed"
    assert terminal_state.subjectivity_violation_count == 0
    assert terminal_state.gate_status == "passed"
    assert terminal_state.gate_reasons == []
    assert terminal_state.latency_status == "passed"
    assert terminal_state.latency_reasons == []


def _stale_gauntlet_summary():
    """Build a valid summary with one abnormal stale-command match."""
    schedule = build_gauntlet_schedule("smoke", arena_ids=["standard_skeleton_doors"], seeds=[1])
    tournament = TournamentSummary(
        tournament_id=schedule.gauntlet_id,
        generated_at="2026-07-16T00:00:00+00:00",
        elo_config=EloConfig(),
        arena_ids=["standard_skeleton_doors"],
        matches=[
            TournamentMatchRecord(
                match_id=f"{schedule.gauntlet_id}-0000",
                arena_id="standard_skeleton_doors",
                random_seed=1,
                hero_first=True,
                status="encounter_ended",
                command_count=8,
                elapsed_ms=12.0,
                outcome="heroes",
                command_status_counts={"accepted": 7, "stale": 1},
                subjectivity_status="passed",
                run_artifact_path="runs/stale.json",
            )
        ],
    )
    stream = GauntletEventStream()
    stream.append(event_type="GAUNTLET_STARTED", gauntlet_id=schedule.gauntlet_id, status="running")
    stream.append(
        event_type="MATCH_FAILED",
        gauntlet_id=schedule.gauntlet_id,
        match_id=f"{schedule.gauntlet_id}-0000",
        match_index=0,
        status="encounter_ended",
        message="stale_command",
    )
    return build_gauntlet_summary(schedule, tournament, stream.since(0))


def _latency_summary(
    *,
    max_command_total_ms: float | None,
    max_local_decision_ms: float | None,
):
    """Build a clean tactical summary with controlled latency metrics."""
    schedule = build_gauntlet_schedule("smoke", arena_ids=["standard_skeleton_doors"], seeds=[1])
    tournament = TournamentSummary(
        tournament_id=schedule.gauntlet_id,
        generated_at="2026-07-16T00:00:00+00:00",
        elo_config=EloConfig(),
        arena_ids=["standard_skeleton_doors"],
        matches=[
            TournamentMatchRecord(
                match_id=f"{schedule.gauntlet_id}-0000",
                arena_id="standard_skeleton_doors",
                random_seed=1,
                hero_first=True,
                status="encounter_ended",
                command_count=1,
                elapsed_ms=2.0,
                outcome="heroes",
                command_status_counts={"accepted": 1},
                subjectivity_status="passed",
                max_command_total_ms=max_command_total_ms,
                max_server_command_ms=2.0,
                max_local_decision_ms=max_local_decision_ms,
                command_total_samples_ms=[] if max_command_total_ms is None else [max_command_total_ms],
                server_command_samples_ms=[2.0],
                local_decision_samples_ms=[] if max_local_decision_ms is None else [max_local_decision_ms],
                command_total_p95_ms=max_command_total_ms,
                command_total_p99_ms=max_command_total_ms,
                server_command_p95_ms=2.0,
                server_command_p99_ms=2.0,
                local_decision_p95_ms=max_local_decision_ms,
                local_decision_p99_ms=max_local_decision_ms,
            )
        ],
    )
    return build_gauntlet_summary(schedule, tournament)
