from ai.evaluation.constants import REQUIRED_SUBJECTIVITY_VALIDATOR
from ai.evaluation.elo_matrix import build_elo_matrix_schedule
from ai.evaluation.elo_runner import run_elo_gauntlet, validate_elo_summary
from ai.policy.source import POLICY_VERSION


def test_elo_matrix_real_smoke_runs_tiny_vertical_slice(tmp_path) -> None:
    schedule = build_elo_matrix_schedule(
        mode="elo_smoke",
        arena_ids=["standard_skeleton_doors", "srd_low_cr_patrol"],
        seeds=[1],
        side_orders=(True, False),
    )

    summary = run_elo_gauntlet(
        schedule,
        max_commands=1,
        summary_output_directory=tmp_path,
        resume=False,
    )

    validate_elo_summary(summary)
    assert summary.scheduled_count == 4
    assert summary.completed_count == 4
    assert summary.pending_count == 0
    assert len(summary.matches) == 4
    assert (tmp_path / "latest.json").exists()
    assert all(match.arena_manifest is not None for match in summary.matches)


def test_elo_matrix_real_match_reaches_natural_rating_eligible_result(tmp_path) -> None:
    schedule = build_elo_matrix_schedule(
        mode="elo_smoke",
        arena_ids=["standard_skeleton_doors"],
        seeds=[1],
        side_orders=(True,),
    )

    summary = run_elo_gauntlet(
        schedule,
        max_commands=240,
        summary_output_directory=tmp_path,
        resume=False,
        require_complete=True,
        require_rating_eligible=True,
    )
    match = summary.matches[0]

    assert summary.gate_status == "passed"
    assert match.base_record is not None
    assert match.base_record.status == "encounter_ended"
    assert match.eligibility.rating_eligible is True
    assert match.runtime_policy_version == POLICY_VERSION
    assert match.runtime_subjectivity_validator == REQUIRED_SUBJECTIVITY_VALIDATOR


def test_real_match_with_false_schedule_policy_identity_is_not_rated(tmp_path) -> None:
    schedule = build_elo_matrix_schedule(
        mode="elo_smoke",
        arena_ids=["standard_skeleton_doors"],
        seeds=[1],
        side_orders=(True,),
        policy_version="deliberately-wrong-policy",
    )

    summary = run_elo_gauntlet(
        schedule,
        max_commands=240,
        summary_output_directory=tmp_path,
        resume=False,
    )
    match = summary.matches[0]

    assert match.runtime_policy_version == POLICY_VERSION
    assert match.eligibility.rating_eligible is False
    assert "policy_version_mismatch" in match.eligibility.reasons
