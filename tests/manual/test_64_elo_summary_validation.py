import pytest

from ai.evaluation import elo_runner
from ai.evaluation.elo_contract import EloEligibility, EloGauntletSummary, EloMatchRecord
from ai.evaluation.elo_matrix import build_elo_matrix_schedule
from ai.evaluation.elo_ratings import EloLedgerBook


def test_elo_summary_validation_accepts_consistent_summary() -> None:
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

    assert elo_runner.validate_elo_summary(summary) is summary
    assert summary.completed_count == 1
    assert summary.skipped_rating_count == 1
    assert summary.failure_rows


def test_elo_summary_validation_rejects_counter_mismatch() -> None:
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
    broken = EloGauntletSummary.model_validate(summary.model_dump(mode="json") | {"completed_count": 0})

    with pytest.raises(ValueError, match="completed_count"):
        elo_runner.validate_elo_summary(broken)


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
