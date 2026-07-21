import json

from ai.evaluation import elo_runner
from ai.evaluation.elo_contract import EloEligibility, EloMatchRecord
from ai.evaluation.elo_dashboard_projection import project_elo_dashboard, project_elo_dashboard_from_file
from ai.evaluation.elo_matrix import build_elo_matrix_schedule
from ai.evaluation.elo_ratings import EloLedgerBook


def test_elo_dashboard_projection_reads_summary_json_only(tmp_path) -> None:
    schedule = build_elo_matrix_schedule(
        mode="elo_smoke",
        arena_ids=["standard_skeleton_doors"],
        seeds=[1],
        side_orders=(True,),
    )
    record = _fake_record("m0", schedule.entries[0])
    summary = elo_runner._build_summary(
        schedule=schedule,
        records=[record],
        ledger_book=EloLedgerBook(),
        events=[],
        generated_at="2026-01-01T00:00:00+00:00",
    )
    path = tmp_path / "summary.json"
    path.write_text(summary.model_dump_json(indent=2), encoding="utf-8")

    projection = project_elo_dashboard_from_file(path)

    assert projection["source"]["kind"] == "elo_gauntlet_summary"
    assert projection["status"]["scheduled_count"] == 1
    assert projection["status"]["skipped_rating_count"] == 1
    assert projection["coverage"]["arena_ids_scheduled"] == ["standard_skeleton_doors"]
    assert projection["failures"][0]["match_id"] == "m0"


def test_elo_dashboard_projection_groups_ledgers() -> None:
    schedule = build_elo_matrix_schedule(
        mode="elo_smoke",
        arena_ids=["standard_skeleton_doors"],
        seeds=[1],
        side_orders=(True,),
    )
    record = _fake_record("m0", schedule.entries[0])
    summary = elo_runner._build_summary(
        schedule=schedule,
        records=[record],
        ledger_book=EloLedgerBook(),
        events=[],
        generated_at="2026-01-01T00:00:00+00:00",
    )

    projection = project_elo_dashboard(summary)

    assert "setup_side" in projection["ledgers"]
    assert "failure_rows" not in projection
    assert projection["failures"]


def test_runner_writes_compact_dashboard_files_without_forensic_match_payloads(
    monkeypatch,
    tmp_path,
) -> None:
    schedule = build_elo_matrix_schedule(
        mode="elo_smoke",
        arena_ids=["standard_skeleton_doors"],
        seeds=[1],
        side_orders=(True,),
    )

    def fake_run_one_entry(**kwargs):
        return _fake_record(kwargs["match_id"], kwargs["entry"])

    monkeypatch.setattr(elo_runner, "_run_one_entry", fake_run_one_entry)
    summary = elo_runner.run_elo_gauntlet(schedule, summary_output_directory=tmp_path)
    matrix_projection = tmp_path / schedule.matrix_id / "dashboard.json"
    latest_projection = tmp_path / "latest.dashboard.json"

    retained = project_elo_dashboard_from_file(tmp_path / schedule.matrix_id / "summary.json")
    compact = json.loads(matrix_projection.read_text(encoding="utf-8"))

    assert matrix_projection.exists()
    assert latest_projection.exists()
    assert compact == summary.dashboard_projection
    assert compact["status"]["completed_count"] == 1
    assert compact["outcomes"][0]["match_id"] == "{}-0000".format(schedule.matrix_id)
    assert "matches" not in compact
    assert retained["status"] == compact["status"]


def _fake_record(match_id: str, entry) -> EloMatchRecord:
    return EloMatchRecord(
        match_id=match_id,
        match_index=entry.match_index,
        schedule_entry=entry,
        arena_manifest=None,
        base_record=None,
        participants=[],
        eligibility=EloEligibility(
            status="skipped",
            rating_eligible=False,
            reasons=["fake"],
            subjectivity_status="not_run",
            runner_status="fake",
            command_status_counts={},
            encounter_finished=False,
            command_cap_reached=False,
            crashed=False,
            timed_out=False,
            has_unknown_outcome=True,
        ),
        friction_flags=["fake"],
    )
