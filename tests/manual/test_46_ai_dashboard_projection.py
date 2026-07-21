"""Regression contracts for JSON-artifact dashboard projection."""

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path

from ai.evaluation.artifacts import ValidationRunArtifact
from ai.evaluation.dashboard_projection import (
    DashboardArtifactSource,
    load_direct_codex_sources,
    load_artifact_sources,
    project_dashboard_stats,
    write_projected_dashboard_stats,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_DIRECTORY = REPOSITORY_ROOT / "ai" / "evidence" / "runs"
DIRECT_CODEX_ARTIFACT_DIRECTORY = REPOSITORY_ROOT / "ai" / "evidence" / "direct_codex_runs"


def _artifact(name: str) -> ValidationRunArtifact:
    """Load one immutable repository artifact for projection tests."""
    path = ARTIFACT_DIRECTORY / name
    return ValidationRunArtifact.model_validate_json(path.read_text(encoding="utf-8"))


def _source(name: str) -> DashboardArtifactSource:
    """Load one artifact with its exact byte hash and dashboard path."""
    path = ARTIFACT_DIRECTORY / name
    content = path.read_bytes()
    return DashboardArtifactSource(
        relative_path=f"evidence/runs/{name}",
        content_sha256=sha256(content).hexdigest(),
        artifact=ValidationRunArtifact.model_validate_json(content),
    )


def test_projection_preserves_manual_rows_and_derives_artifact_metrics() -> None:
    """Generated rows are deterministic measured views, not manual statistics."""
    represented_name = "20260713-phase3c-sorcerer-barbarian-seed8675309.json"
    door_name = "20260713-phase4-double-door-dark-hunt-seed8675310.json"
    duel_name = "20260713-phase4b-sorcerer-barbarian-seed8675311.json"
    base = {
        "schema_version": 1,
        "updated_at": "2026-07-13T12:00:00+00:00",
        "source_log": "AGENT_UX_ITERATION_LOG.md",
        "notes": [],
        "iterations": [
            {
                "id": "manual-row",
                "sequence": 10,
                "artifact": f"evidence/runs/{represented_name}",
                "metrics": {"human_annotation": 1},
            },
            {
                "id": "stale-generated-row",
                "sequence": 11,
                "generated_from_artifact": True,
                "artifact_run_id": "obsolete",
                "metrics": {"fabricated": 1},
            },
        ],
        "latest_integrated_changes": ["Human-authored change"],
        "next_targets": ["Human-authored target"],
    }
    sources = [_source(represented_name), _source(door_name), _source(duel_name)]
    door_source = sources[1]
    door_traces = [
        trace.model_copy(update={"server_timing": {}})
        for trace in door_source.artifact.result.traces
    ]
    door_traces[0] = door_traces[0].model_copy(update={
        "server_timing": {
            "total_ms": 21.5,
            "phases": {
                "publish.followup_epoch.build_decision_epoch_total_ms": 9.5,
            },
        },
        "action_server_timing": {
            "command_type": "action_execute",
            "total_ms": 12.5,
            "phases": {
                "execute_by_index_ms": 8.0,
                "execute_by_index.grid.compute_paths.dijkstra_total_ms": 3.0,
            },
        }
    })
    sources[1] = door_source.model_copy(update={
        "artifact": door_source.artifact.model_copy(update={
            "result": door_source.artifact.result.model_copy(update={"traces": door_traces}),
            "performance": door_source.artifact.performance.model_copy(update={
                "normal_stages": {
                    "local_decision_ms": door_source.artifact.performance.stages["local_decision_ms"],
                    "total_ms": door_source.artifact.performance.stages["total_ms"],
                },
                "diagnostic_stages": {
                    "total_ms": door_source.artifact.performance.stages["total_ms"],
                },
            }),
        })
    })

    projected = project_dashboard_stats(deepcopy(base), sources)

    assert projected["schema_version"] == 2
    assert projected["latest_integrated_changes"] == ["Human-authored change"]
    assert projected["next_targets"] == ["Human-authored target"]
    assert projected["source_log"] == (
        "AGENT_UX_ITERATION_LOG.md + evidence/runs/*.json + "
        "evidence/direct_codex_runs/*.json"
    )
    assert [row["id"] for row in projected["iterations"]] == ["manual-row"]
    assert [row["sequence"] for row in projected["iterations"]] == [10]
    assert [row["run_index"] for row in projected["runs"]] == [1, 2, 3]
    assert {row["run_id"] for row in projected["runs"]} == {
        source.artifact.run_id for source in sources
    }

    door_row = next(
        row for row in projected["runs"]
        if row["run_id"] == sources[1].artifact.run_id
    )
    door_metrics = door_row["metrics"]
    door_artifact = sources[1].artifact
    assert door_row["artifact_sha256"] == sources[1].content_sha256
    assert door_row["result"]["status"] == "encounter_ended"
    assert door_metrics["external_selfplay_commands"] == door_artifact.command_summary.total
    assert door_metrics["external_selfplay_nonaccepted_commands"] == 0
    assert door_metrics["subjectivity_audit_passed"] == 1
    assert door_metrics["subjectivity_violation_count"] == 0
    assert door_metrics["local_decision_p95_ms"] == door_artifact.performance.stages["local_decision_ms"].p95_ms
    assert door_metrics["max_command_total_ms"] == door_artifact.performance.stages["total_ms"].max_ms
    assert door_metrics["total_command_max_ms"] == door_metrics["max_command_total_ms"]
    assert door_metrics["max_server_command_ms"] == 21.5
    assert door_metrics["server_command_max_ms"] == 21.5
    assert door_metrics["server_command_sample_count"] == 1
    assert door_metrics[
        "server_phase_max_publish_followup_epoch_build_decision_epoch_total_ms"
    ] == 9.5
    assert (
        door_metrics["normal_local_decision_p95_ms"]
        == door_artifact.performance.normal_stages["local_decision_ms"].p95_ms
    )
    assert (
        door_metrics["normal_total_max_ms"]
        == door_artifact.performance.normal_stages["total_ms"].max_ms
    )
    assert (
        door_metrics["diagnostic_total_p95_ms"]
        == door_artifact.performance.diagnostic_stages["total_ms"].p95_ms
    )
    assert door_metrics["typed_routine_command_count"] > 0
    assert door_metrics["tag_count_information_gain"] > 0
    assert door_metrics["action_phase_max_execute_by_index_ms"] == 8.0
    assert door_metrics[
        "action_phase_max_execute_by_index_grid_compute_paths_dijkstra_total_ms"
    ] == 3.0

    assert project_dashboard_stats(deepcopy(projected), sources) == projected


def test_projection_derives_direct_codex_metrics_without_inventing_claims() -> None:
    """Direct play contributes measured series while absent claims remain null."""
    direct_sources = load_direct_codex_sources(DIRECT_CODEX_ARTIFACT_DIRECTORY)

    projected = project_dashboard_stats(
        {"iterations": [], "notes": []},
        [],
        direct_sources,
    )

    expected_run_ids = {
        "20260713-rotation-01-codex-barbarian-vs-ai",
        "20260713-rotation-02-codex-sorcerer-vs-ai",
        "20260713-rotation-03-codex-skeletons-vs-ai-barbarian",
        "20260713-rotation-04-codex-skeletons-vs-ai-sorcerer",
    }
    projected_run_ids = {row["run_id"] for row in projected["runs"]}
    assert expected_run_ids <= projected_run_ids
    assert projected["projection"]["direct_codex_run_count"] == len(direct_sources)
    assert [row["run_index"] for row in projected["runs"]] == list(
        range(1, len(direct_sources) + 1)
    )
    sorcerer = next(
        row for row in projected["runs"]
        if row["run_id"] == "20260713-rotation-02-codex-sorcerer-vs-ai"
    )
    assert sorcerer["artifact_type"] == "direct_codex_run"
    assert sorcerer["policy"] is None
    assert sorcerer["subjectivity"] is None
    assert sorcerer["command_summary"] == {
        "total": 16,
        "accepted": 16,
        "rejected": 0,
        "stale": 0,
        "error": 0,
        "missing_result": 0,
    }
    assert sorcerer["metrics"]["observation_frame_count"] == 210
    assert sorcerer["metrics"]["agent_event_count"] == 86
    assert sorcerer["metrics"]["manual_friction_count"] == 7
    assert sorcerer["metrics"]["total_sample_count"] == 16
    assert sorcerer["metrics"]["command_submit_sample_count"] == 16
    assert sorcerer["metrics"]["friction_count_latency_regression"] == 2
    assert "subjectivity_audit_passed" not in sorcerer["metrics"]
    assert "subjectivity_violation_count" not in sorcerer["metrics"]

    skeletons = next(
        row for row in projected["runs"]
        if row["run_id"] == "20260713-rotation-03-codex-skeletons-vs-ai-barbarian"
    )
    assert skeletons["command_summary"]["accepted"] == 14
    assert skeletons["metrics"]["observation_frame_count"] == 275
    assert skeletons["metrics"]["agent_event_count"] == 79
    assert skeletons["metrics"]["manual_friction_count"] == 9

    skeletons_vs_sorcerer = next(
        row for row in projected["runs"]
        if row["run_id"] == "20260713-rotation-04-codex-skeletons-vs-ai-sorcerer"
    )
    assert skeletons_vs_sorcerer["command_summary"]["accepted"] == 10
    assert skeletons_vs_sorcerer["metrics"]["observation_frame_count"] == 151
    assert skeletons_vs_sorcerer["metrics"]["agent_event_count"] == 56
    assert skeletons_vs_sorcerer["metrics"]["manual_friction_count"] == 3


def test_projection_rejects_conflicting_artifact_identity() -> None:
    """The same run id cannot silently project from different bytes."""
    source = _source("20260713-phase4-double-door-dark-hunt-seed8675310.json")
    conflicting = source.model_copy(update={
        "relative_path": "evidence/runs/conflicting-copy.json",
        "content_sha256": "f" * 64,
    })

    try:
        project_dashboard_stats({"iterations": []}, [source, conflicting])
    except ValueError as error:
        assert source.artifact.run_id in str(error)
    else:
        raise AssertionError("Expected conflicting artifact identity to fail")


def test_projection_writer_is_byte_idempotent(tmp_path: Path) -> None:
    """Repeated projection produces the same JSON bytes and source ordering."""
    stats_path = tmp_path / "stats.json"
    stats_path.write_text(
        json.dumps({
            "schema_version": 1,
            "updated_at": "2026-07-01T00:00:00+00:00",
            "source_log": "AGENT_UX_ITERATION_LOG.md",
            "notes": [],
            "iterations": [],
            "latest_integrated_changes": [],
            "next_targets": [],
        }),
        encoding="utf-8",
    )

    first = write_projected_dashboard_stats(stats_path, ARTIFACT_DIRECTORY)
    first_bytes = stats_path.read_bytes()
    second = write_projected_dashboard_stats(stats_path, ARTIFACT_DIRECTORY)

    assert first == second
    assert stats_path.read_bytes() == first_bytes
    assert [source.relative_path for source in load_artifact_sources(ARTIFACT_DIRECTORY)] == sorted(
        source.relative_path for source in load_artifact_sources(ARTIFACT_DIRECTORY)
    )


def test_dashboard_has_separate_artifact_run_series() -> None:
    """Game-run evidence is rendered independently from human iteration history."""
    html = (REPOSITORY_ROOT / "ai" / "AGENT_UX_ITERATION_DASHBOARD.html").read_text(
        encoding="utf-8"
    )

    assert 'id="run-metrics"' in html
    assert 'id="run-local-latency-chart"' in html
    assert 'id="run-command-latency-chart"' in html
    assert 'id="run-transport-latency-chart"' in html
    assert 'id="run-candidate-pressure-chart"' in html
    assert 'id="run-subjectivity-chart"' in html
    assert 'id="run-rows"' in html
    assert "const runs = data.runs || [];" in html
    assert "renderRunRows(data);" in html
    assert 'indexKey: "run_index"' in html
    assert "function chartMetric" in html
    assert "Number.isFinite(numeric)" in html
