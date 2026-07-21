"""Gauntlet runner CLI checks."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx
import pytest
from typer.testing import CliRunner

from ai.evaluation import gauntlet_runner
from ai.evaluation.gauntlet import build_gauntlet_schedule, build_gauntlet_summary
from ai.evaluation.gauntlet_runner import HttpMirroringGauntletEventSink
from ai.evaluation.tournament import EloConfig, TournamentMatchRecord, TournamentSummary
from ai.external_selfplay import ExternalSelfPlayResult, ExternalSelfPlayTrace


def test_gauntlet_runner_schedule_prints_repeatable_json() -> None:
    """The CLI should expose deterministic schedules without running matches."""
    runner = CliRunner()

    result = runner.invoke(
        gauntlet_runner.app,
        [
            "schedule",
            "--mode",
            "rotation",
            "--arena-id",
            "standard_skeleton_doors",
            "--seed",
            "11",
            "--seed",
            "12",
            "--policy-version",
            "policy-cli-test",
        ],
    )
    payload = json.loads(result.stdout)

    assert result.exit_code == 0
    assert payload["mode"] == "rotation"
    assert payload["entries"][0]["arena_id"] == "standard_skeleton_doors"
    assert [entry["random_seed"] for entry in payload["entries"]] == [11, 12]
    assert {entry["policy_version"] for entry in payload["entries"]} == {"policy-cli-test"}


def test_gauntlet_runner_schedule_can_replay_retained_failures(tmp_path: Path) -> None:
    """The CLI should turn retained failure JSON into a regression schedule."""
    source_schedule = build_gauntlet_schedule("smoke", arena_ids=["standard_skeleton_doors"], seeds=[7])
    tournament = TournamentSummary(
        tournament_id=source_schedule.gauntlet_id,
        generated_at="2026-07-16T00:00:00+00:00",
        elo_config=EloConfig(),
        arena_ids=["standard_skeleton_doors"],
        matches=[
            TournamentMatchRecord(
                match_id=f"{source_schedule.gauntlet_id}-0000",
                arena_id="standard_skeleton_doors",
                random_seed=7,
                hero_first=True,
                status="subjectivity_leak",
                command_count=4,
                elapsed_ms=9.0,
                outcome="unknown",
            )
        ],
    )
    summary = build_gauntlet_summary(source_schedule, tournament)
    summary_path = tmp_path / "failed-summary.json"
    summary_path.write_text(summary.model_dump_json(), encoding="utf-8")
    runner = CliRunner()

    result = runner.invoke(
        gauntlet_runner.app,
        [
            "schedule",
            "--mode",
            "regression",
            "--regression-source",
            str(summary_path),
            "--policy-version",
            "retry-policy",
        ],
    )
    payload = json.loads(result.stdout)

    assert result.exit_code == 0
    assert payload["mode"] == "regression"
    assert len(payload["entries"]) == 1
    assert payload["entries"][0]["random_seed"] == 7
    assert payload["entries"][0]["policy_version"] == "retry-policy"
    assert "status:subjectivity_leak" in payload["entries"][0]["tags"]


def test_gauntlet_runner_run_writes_raw_artifacts_and_latest_summary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The CLI run command should retain raw match JSON and compact latest summary JSON."""
    def fake_selfplay(
        arena_id: str,
        *,
        max_commands: int,
        hero_first: bool,
        random_seed: int,
    ) -> ExternalSelfPlayResult:
        return ExternalSelfPlayResult(
            arena_id=arena_id,
            status="encounter_ended",
            command_count=max_commands,
            elapsed_ms=2.25,
            session_ids_by_faction={"heroes": "hero-session", "monsters": "monster-session"},
            final_hp_by_actor={"Hero": 10, "Skeleton": 0},
            final_faction_by_actor={"Hero": "heroes", "Skeleton": "monsters"},
            traces=[
                _trace(
                    "accepted",
                    total_ms=6.0,
                    local_decision_ms=1.5,
                    server_ms=3.25,
                )
            ],
        )

    runs_dir = tmp_path / "runs"
    gauntlets_dir = tmp_path / "gauntlets"
    monkeypatch.setattr("ai.evaluation.gauntlet.run_external_selfplay", fake_selfplay)
    runner = CliRunner()

    result = runner.invoke(
        gauntlet_runner.app,
        [
            "run",
            "--mode",
            "smoke",
            "--arena-id",
            "standard_skeleton_doors",
            "--seed",
            "44",
            "--max-commands",
            "3",
            "--runs-output-directory",
            str(runs_dir),
            "--gauntlet-output-directory",
            str(gauntlets_dir),
        ],
    )
    payload = json.loads(result.stdout)
    latest_payload = json.loads((gauntlets_dir / "latest.json").read_text(encoding="utf-8"))
    run_artifacts = list(runs_dir.glob("*.json"))

    assert result.exit_code == 0
    assert payload["mode"] == "smoke"
    assert payload["completed_count"] == 1
    assert payload["performance"]["total_command_count"] == 3
    assert payload["performance"]["max_command_total_ms"] == 6.0
    assert payload["performance"]["max_server_command_ms"] == 3.25
    assert payload["performance"]["max_local_decision_ms"] == 1.5
    assert payload["performance"]["normal_command_total_sample_count"] == 1
    assert payload["performance"]["diagnostic_command_total_sample_count"] == 0
    assert payload["performance"]["command_total_p95_ms"] == 6.0
    assert payload["performance"]["command_total_p99_ms"] == 6.0
    assert payload["performance"]["normal_command_total_p95_ms"] == 6.0
    assert payload["performance"]["normal_command_total_p99_ms"] == 6.0
    assert payload["performance"]["diagnostic_command_total_p95_ms"] is None
    assert payload["performance"]["local_decision_p95_ms"] == 1.5
    assert payload["performance"]["local_decision_p99_ms"] == 1.5
    assert payload["latency_status"] == "failed"
    assert payload["latency_reasons"] == ["command_total_p95_over_5ms"]
    assert payload["artifact_paths"]
    assert latest_payload["gauntlet_id"] == payload["gauntlet_id"]
    assert latest_payload["matches"][0]["max_server_command_ms"] == 3.25
    assert latest_payload["matches"][0]["normal_command_total_samples_ms"] == [6.0]
    assert len(run_artifacts) == 1


def test_gauntlet_runner_uses_content_sized_default_command_cap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Content gauntlets should not inherit the short smoke command cap."""
    observed_max_commands: list[int] = []

    def fake_selfplay(
        arena_id: str,
        *,
        max_commands: int,
        hero_first: bool,
        random_seed: int,
    ) -> ExternalSelfPlayResult:
        observed_max_commands.append(max_commands)
        return ExternalSelfPlayResult(
            arena_id=arena_id,
            status="encounter_ended",
            command_count=2,
            elapsed_ms=1.0,
            session_ids_by_faction={"heroes": "hero-session"},
            final_hp_by_actor={"Hero": 10, "Skeleton": 0},
            final_faction_by_actor={"Hero": "heroes", "Skeleton": "monsters"},
            traces=[_trace("accepted")],
        )

    monkeypatch.setattr("ai.evaluation.gauntlet.run_external_selfplay", fake_selfplay)
    runner = CliRunner()

    result = runner.invoke(
        gauntlet_runner.app,
        [
            "run",
            "--mode",
            "content",
            "--arena-id",
            "srd_undead_crypt",
            "--seed",
            "1",
            "--no-run-artifacts",
            "--no-summary-file",
        ],
    )

    assert result.exit_code == 0
    assert observed_max_commands == [200]


def test_gauntlet_runner_require_gate_pass_succeeds_for_clean_summary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Release automation can require a green gauntlet gate."""
    def fake_selfplay(
        arena_id: str,
        *,
        max_commands: int,
        hero_first: bool,
        random_seed: int,
    ) -> ExternalSelfPlayResult:
        return ExternalSelfPlayResult(
            arena_id=arena_id,
            status="encounter_ended",
            command_count=1,
            elapsed_ms=1.0,
            session_ids_by_faction={"heroes": "hero-session"},
            final_hp_by_actor={"Hero": 10, "Skeleton": 0},
            final_faction_by_actor={"Hero": "heroes", "Skeleton": "monsters"},
            traces=[_trace("accepted")],
        )

    monkeypatch.setattr("ai.evaluation.gauntlet.run_external_selfplay", fake_selfplay)
    runner = CliRunner()

    result = runner.invoke(
        gauntlet_runner.app,
        [
            "run",
            "--mode",
            "smoke",
            "--arena-id",
            "standard_skeleton_doors",
            "--seed",
            "44",
            "--max-commands",
            "1",
            "--no-run-artifacts",
            "--no-summary-file",
            "--require-gate-pass",
        ],
    )
    payload = json.loads(result.stdout)

    assert result.exit_code == 0
    assert payload["gate_status"] == "passed"
    assert payload["gate_reasons"] == []


def test_gauntlet_runner_require_gate_pass_fails_after_writing_summary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A red gate should be automation-failing while retaining its JSON evidence."""
    def fake_selfplay(
        arena_id: str,
        *,
        max_commands: int,
        hero_first: bool,
        random_seed: int,
    ) -> ExternalSelfPlayResult:
        return ExternalSelfPlayResult(
            arena_id=arena_id,
            status="encounter_ended",
            command_count=1,
            elapsed_ms=1.0,
            session_ids_by_faction={"heroes": "hero-session"},
            final_hp_by_actor={"Hero": 10, "Skeleton": 0},
            final_faction_by_actor={"Hero": "heroes", "Skeleton": "monsters"},
            traces=[_trace("stale")],
        )

    gauntlets_dir = tmp_path / "gauntlets"
    monkeypatch.setattr("ai.evaluation.gauntlet.run_external_selfplay", fake_selfplay)
    runner = CliRunner()

    result = runner.invoke(
        gauntlet_runner.app,
        [
            "run",
            "--mode",
            "smoke",
            "--arena-id",
            "standard_skeleton_doors",
            "--seed",
            "44",
            "--max-commands",
            "1",
            "--no-run-artifacts",
            "--gauntlet-output-directory",
            str(gauntlets_dir),
            "--require-gate-pass",
        ],
    )
    payload = json.loads(result.stdout)
    latest_payload = json.loads((gauntlets_dir / "latest.json").read_text(encoding="utf-8"))

    assert result.exit_code == 2
    assert payload["gate_status"] == "failed"
    assert payload["gate_reasons"] == ["failed_matches", "stale_commands"]
    assert latest_payload["gauntlet_id"] == payload["gauntlet_id"]
    assert latest_payload["gate_status"] == "failed"


def test_gauntlet_runner_check_validates_retained_green_summary(tmp_path: Path) -> None:
    """Retained green summaries should be checkable without rerunning matches."""
    schedule = build_gauntlet_schedule("smoke", arena_ids=["standard_skeleton_doors"], seeds=[7])
    tournament = TournamentSummary(
        tournament_id=schedule.gauntlet_id,
        generated_at="2026-07-16T00:00:00+00:00",
        elo_config=EloConfig(),
        arena_ids=["standard_skeleton_doors"],
        matches=[
            TournamentMatchRecord(
                match_id=f"{schedule.gauntlet_id}-0000",
                arena_id="standard_skeleton_doors",
                random_seed=7,
                hero_first=True,
                status="encounter_ended",
                command_count=2,
                elapsed_ms=4.0,
                outcome="heroes",
                command_status_counts={"accepted": 2},
                subjectivity_status="passed",
            )
        ],
    )
    summary = build_gauntlet_summary(schedule, tournament)
    summary_path = tmp_path / "green-summary.json"
    summary_path.write_text(summary.model_dump_json(), encoding="utf-8")
    runner = CliRunner()

    result = runner.invoke(
        gauntlet_runner.app,
        ["check", str(summary_path), "--require-gate-pass"],
    )
    payload = json.loads(result.stdout)

    assert result.exit_code == 0
    assert payload["gate_status"] == "passed"
    assert payload["latency_status"] == "failed"
    assert payload["latency_reasons"] == ["missing_command_total_latency", "missing_local_decision_latency"]


def test_gauntlet_runner_check_fails_retained_red_summary(tmp_path: Path) -> None:
    """Retained red summaries should fail automation without hiding their JSON."""
    schedule = build_gauntlet_schedule("smoke", arena_ids=["standard_skeleton_doors"], seeds=[7])
    tournament = TournamentSummary(
        tournament_id=schedule.gauntlet_id,
        generated_at="2026-07-16T00:00:00+00:00",
        elo_config=EloConfig(),
        arena_ids=["standard_skeleton_doors"],
        matches=[
            TournamentMatchRecord(
                match_id=f"{schedule.gauntlet_id}-0000",
                arena_id="standard_skeleton_doors",
                random_seed=7,
                hero_first=True,
                status="command_cap_reached",
                command_count=2,
                elapsed_ms=4.0,
                outcome="unknown",
                command_status_counts={"accepted": 2},
                subjectivity_status="passed",
            )
        ],
    )
    summary = build_gauntlet_summary(schedule, tournament)
    summary_path = tmp_path / "red-summary.json"
    summary_path.write_text(summary.model_dump_json(), encoding="utf-8")
    runner = CliRunner()

    result = runner.invoke(
        gauntlet_runner.app,
        ["check", str(summary_path), "--require-gate-pass"],
    )
    payload = json.loads(result.stdout)

    assert result.exit_code == 2
    assert payload["gate_status"] == "failed"
    assert payload["gate_reasons"] == ["failed_matches"]


def test_gauntlet_runner_check_rejects_false_green_summary(tmp_path: Path) -> None:
    """A passed gate claim should not override contradictory retained rows."""
    schedule = build_gauntlet_schedule("smoke", arena_ids=["standard_skeleton_doors"], seeds=[7])
    tournament = TournamentSummary(
        tournament_id=schedule.gauntlet_id,
        generated_at="2026-07-16T00:00:00+00:00",
        elo_config=EloConfig(),
        arena_ids=["standard_skeleton_doors"],
        matches=[
            TournamentMatchRecord(
                match_id=f"{schedule.gauntlet_id}-0000",
                arena_id="standard_skeleton_doors",
                random_seed=7,
                hero_first=True,
                status="encounter_ended",
                command_count=2,
                elapsed_ms=4.0,
                outcome="heroes",
                command_status_counts={"accepted": 2},
                subjectivity_status="passed",
            )
        ],
    )
    summary = build_gauntlet_summary(schedule, tournament)
    corrupt = summary.model_copy(update={"command_status_counts": {"accepted": 99}})
    summary_path = tmp_path / "false-green-summary.json"
    summary_path.write_text(corrupt.model_dump_json(), encoding="utf-8")
    runner = CliRunner()

    result = runner.invoke(
        gauntlet_runner.app,
        ["check", str(summary_path), "--require-gate-pass"],
    )

    assert result.exit_code != 0
    assert isinstance(result.exception, ValueError)
    assert "command status counts" in str(result.exception)


def test_gauntlet_runner_check_can_require_latency_pass(tmp_path: Path) -> None:
    """Speed-sensitive automation should fail slow retained summaries separately."""
    schedule = build_gauntlet_schedule("smoke", arena_ids=["standard_skeleton_doors"], seeds=[7])
    tournament = TournamentSummary(
        tournament_id=schedule.gauntlet_id,
        generated_at="2026-07-16T00:00:00+00:00",
        elo_config=EloConfig(),
        arena_ids=["standard_skeleton_doors"],
        matches=[
            TournamentMatchRecord(
                match_id=f"{schedule.gauntlet_id}-0000",
                arena_id="standard_skeleton_doors",
                random_seed=7,
                hero_first=True,
                status="encounter_ended",
                command_count=2,
                elapsed_ms=4.0,
                outcome="heroes",
                command_status_counts={"accepted": 2},
                subjectivity_status="passed",
                max_command_total_ms=12.0,
                max_server_command_ms=8.0,
                max_local_decision_ms=6.0,
                command_total_samples_ms=[12.0],
                server_command_samples_ms=[8.0],
                local_decision_samples_ms=[6.0],
                command_total_p95_ms=12.0,
                command_total_p99_ms=12.0,
                server_command_p95_ms=8.0,
                server_command_p99_ms=8.0,
                local_decision_p95_ms=6.0,
                local_decision_p99_ms=6.0,
            )
        ],
    )
    summary = build_gauntlet_summary(schedule, tournament)
    summary_path = tmp_path / "slow-summary.json"
    summary_path.write_text(summary.model_dump_json(), encoding="utf-8")
    runner = CliRunner()

    result = runner.invoke(
        gauntlet_runner.app,
        ["check", str(summary_path), "--require-gate-pass", "--require-latency-pass"],
    )
    payload = json.loads(result.stdout)

    assert result.exit_code == 3
    assert payload["gate_status"] == "passed"
    assert payload["latency_status"] == "failed"
    assert payload["latency_reasons"] == [
        "command_total_p95_over_5ms",
        "command_total_p99_over_10ms",
        "local_decision_p99_over_5ms",
    ]


def test_gauntlet_runner_check_latency_prefers_normal_samples(tmp_path: Path) -> None:
    """Retained diagnostic probes should remain visible without failing the speed gate."""
    schedule = build_gauntlet_schedule("smoke", arena_ids=["standard_skeleton_doors"], seeds=[7])
    tournament = TournamentSummary(
        tournament_id=schedule.gauntlet_id,
        generated_at="2026-07-16T00:00:00+00:00",
        elo_config=EloConfig(),
        arena_ids=["standard_skeleton_doors"],
        matches=[
            TournamentMatchRecord(
                match_id=f"{schedule.gauntlet_id}-0000",
                arena_id="standard_skeleton_doors",
                random_seed=7,
                hero_first=True,
                status="encounter_ended",
                command_count=2,
                elapsed_ms=4.0,
                outcome="heroes",
                command_status_counts={"accepted": 2},
                subjectivity_status="passed",
                max_command_total_ms=60.0,
                max_server_command_ms=50.0,
                max_local_decision_ms=4.0,
                command_total_samples_ms=[4.0, 60.0],
                server_command_samples_ms=[2.0, 50.0],
                local_decision_samples_ms=[2.0, 4.0],
                normal_command_total_samples_ms=[4.0],
                normal_server_command_samples_ms=[2.0],
                normal_local_decision_samples_ms=[2.0],
                diagnostic_command_total_samples_ms=[60.0],
                diagnostic_server_command_samples_ms=[50.0],
                diagnostic_local_decision_samples_ms=[4.0],
                command_total_p95_ms=60.0,
                command_total_p99_ms=60.0,
                server_command_p95_ms=50.0,
                server_command_p99_ms=50.0,
                local_decision_p95_ms=4.0,
                local_decision_p99_ms=4.0,
                normal_command_total_p95_ms=4.0,
                normal_command_total_p99_ms=4.0,
                normal_server_command_p95_ms=2.0,
                normal_server_command_p99_ms=2.0,
                normal_local_decision_p95_ms=2.0,
                normal_local_decision_p99_ms=2.0,
                diagnostic_command_total_p95_ms=60.0,
                diagnostic_command_total_p99_ms=60.0,
                diagnostic_server_command_p95_ms=50.0,
                diagnostic_server_command_p99_ms=50.0,
                diagnostic_local_decision_p95_ms=4.0,
                diagnostic_local_decision_p99_ms=4.0,
            )
        ],
    )
    summary = build_gauntlet_summary(schedule, tournament)
    summary_path = tmp_path / "diagnostic-summary.json"
    summary_path.write_text(summary.model_dump_json(), encoding="utf-8")
    runner = CliRunner()

    result = runner.invoke(
        gauntlet_runner.app,
        ["check", str(summary_path), "--require-gate-pass", "--require-latency-pass"],
    )
    payload = json.loads(result.stdout)

    assert result.exit_code == 0
    assert payload["latency_status"] == "passed"
    assert payload["performance"]["command_total_p99_ms"] == 60.0
    assert payload["performance"]["normal_command_total_p99_ms"] == 4.0
    assert payload["performance"]["diagnostic_command_total_p99_ms"] == 60.0


def test_http_mirroring_gauntlet_sink_posts_events_and_retains_local_history() -> None:
    """The CLI mirror sink should feed a backend while preserving local summary history."""
    requests: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(json.loads(request.content.decode("utf-8")))
        return httpx.Response(200, json={"events": [], "count": 1, "total": 1, "next_cursor": 1})

    client = httpx.Client(transport=httpx.MockTransport(handler), base_url="http://testserver")
    sink = HttpMirroringGauntletEventSink("http://testserver", client=client)

    event = sink.append(
        event_type="GAUNTLET_STARTED",
        gauntlet_id="mirror-g",
        status="running",
        payload={"mode": "smoke"},
    )

    assert event.cursor == 1
    assert [row.cursor for row in sink.since(0)] == [1]
    assert requests[0]["events"][0]["event_type"] == "GAUNTLET_STARTED"
    assert requests[0]["events"][0]["gauntlet_id"] == "mirror-g"


def _trace(
    status: str,
    *,
    total_ms: float | None = None,
    local_decision_ms: float | None = None,
    server_ms: float | None = None,
) -> ExternalSelfPlayTrace:
    return ExternalSelfPlayTrace(
        command_index=0,
        round_number=1,
        turn_index=0,
        session_id="hero-session",
        actor_uuid="hero-uuid",
        actor_name="Hero",
        actor_faction="heroes",
        entity_action_count=0,
        position_action_count=0,
        command_type="end_turn",
        reason="test command",
        command_status=status,
        total_ms=total_ms,
        local_decision_ms=local_decision_ms,
        server_timing={"total_ms": server_ms} if server_ms is not None else {},
        subjective_known_entity_uuids=["hero-uuid"],
        subjective_known_entity_positions=[],
        subjective_known_object_uuids=[],
        subjective_known_object_positions=[],
        subjective_known_tile_positions=[],
        subjective_affordance_row_ids=[],
        subjective_affordance_target_uuids=[],
        subjective_affordance_target_positions=[],
    )
