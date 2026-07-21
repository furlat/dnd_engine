import json
import time

import pytest

from ai.evaluation import elo_runner
from ai.evaluation.constants import REQUIRED_SUBJECTIVITY_VALIDATOR
from ai.evaluation.elo_contract import (
    ArenaManifest,
    EloEligibility,
    EloMatchFailureArtifact,
    EloMatchRecord,
    EloParticipant,
)
from ai.evaluation.elo_matrix import build_elo_matrix_schedule
from ai.evaluation.tournament import TournamentMatchRecord
from ai.policy.source import CONTROLLER_PROFILE, POLICY_VERSION


def test_elo_runner_resumes_without_rerunning_completed_rows(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    schedule = build_elo_matrix_schedule(
        mode="elo_smoke",
        arena_ids=["standard_skeleton_doors"],
        seeds=[1],
    )
    calls: list[int] = []

    def fake_run_one_entry(**kwargs):
        entry = kwargs["entry"]
        calls.append(entry.match_index)
        return _fake_record(kwargs["match_id"], entry)

    monkeypatch.setattr(elo_runner, "_run_one_entry", fake_run_one_entry)

    first = elo_runner.run_elo_gauntlet(schedule, summary_output_directory=tmp_path, resume=True)
    calls.clear()
    second = elo_runner.run_elo_gauntlet(schedule, summary_output_directory=tmp_path, resume=True)

    assert first.completed_count == 2
    assert second.completed_count == 2
    assert calls == []


def test_elo_runner_refuses_resume_with_schedule_hash_mismatch(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    schedule = build_elo_matrix_schedule(
        mode="elo_smoke",
        arena_ids=["standard_skeleton_doors"],
        seeds=[1],
    )

    def fake_run_one_entry(**kwargs):
        return _fake_record(kwargs["match_id"], kwargs["entry"])

    monkeypatch.setattr(elo_runner, "_run_one_entry", fake_run_one_entry)
    elo_runner.run_elo_gauntlet(schedule, summary_output_directory=tmp_path, resume=True)
    changed = schedule.model_copy(update={"schedule_hash": "different"})

    with pytest.raises(ValueError, match="schedule hash mismatch"):
        elo_runner.run_elo_gauntlet(changed, summary_output_directory=tmp_path, resume=True)


def test_elo_runner_resumes_from_match_files_when_checkpoint_is_stale(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    schedule = build_elo_matrix_schedule(
        mode="elo_smoke",
        arena_ids=["standard_skeleton_doors"],
        seeds=[1],
    )

    def fake_run_one_entry(**kwargs):
        return _fake_record(kwargs["match_id"], kwargs["entry"])

    monkeypatch.setattr(elo_runner, "_run_one_entry", fake_run_one_entry)
    elo_runner.run_elo_gauntlet(schedule, summary_output_directory=tmp_path, resume=True)
    matrix_dir = tmp_path / schedule.matrix_id
    (matrix_dir / "summary.json").unlink()
    (matrix_dir / "checkpoints" / "latest.partial.json").write_text(
        json.dumps({"stale": True}),
        encoding="utf-8",
    )
    calls: list[int] = []

    def fail_if_rerun(**kwargs):
        calls.append(kwargs["entry"].match_index)
        raise AssertionError("completed row was rerun")

    monkeypatch.setattr(elo_runner, "_run_one_entry", fail_if_rerun)
    resumed = elo_runner.run_elo_gauntlet(schedule, summary_output_directory=tmp_path, resume=True)

    assert resumed.completed_count == 2
    assert calls == []


def test_compact_checkpoint_does_not_embed_matches_or_schedule(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    schedule = build_elo_matrix_schedule(
        mode="elo_smoke",
        arena_ids=["standard_skeleton_doors"],
        seeds=[1],
        side_orders=(True,),
    )

    def fake_run_one_entry(**kwargs):
        return _fake_record(kwargs["match_id"], kwargs["entry"])

    monkeypatch.setattr(elo_runner, "_run_one_entry", fake_run_one_entry)
    elo_runner.run_elo_gauntlet(schedule, summary_output_directory=tmp_path, resume=True)
    checkpoint_path = tmp_path / schedule.matrix_id / "checkpoints" / "latest.partial.json"
    checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))

    assert checkpoint["completed_match_indices"] == [0]
    assert checkpoint["pending_count"] == 0
    assert "matches" not in checkpoint
    assert "schedule" not in checkpoint


def test_load_retained_schedule_preserves_matrix_identity(tmp_path) -> None:
    schedule = build_elo_matrix_schedule(
        mode="elo_smoke",
        arena_ids=["standard_skeleton_doors"],
        seeds=[1],
    )
    path = tmp_path / "schedule.json"
    path.write_text(schedule.model_dump_json(indent=2), encoding="utf-8")

    loaded = elo_runner.load_elo_matrix_schedule(path)

    assert loaded == schedule
    assert loaded.matrix_id == schedule.matrix_id


def test_retry_ineligible_archives_prior_attempt_and_replaces_only_failed_row(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    schedule = build_elo_matrix_schedule(
        mode="elo_smoke",
        arena_ids=["standard_skeleton_doors"],
        seeds=[1],
        side_orders=(True,),
    )
    calls: list[int] = []

    def first_attempt(**kwargs):
        return _fake_record(kwargs["match_id"], kwargs["entry"])

    monkeypatch.setattr(elo_runner, "_run_one_entry", first_attempt)
    first = elo_runner.run_elo_gauntlet(schedule, summary_output_directory=tmp_path)
    assert first.skipped_rating_count == 1

    def corrected_attempt(**kwargs):
        calls.append(kwargs["attempt_number"])
        artifact = tmp_path / "corrected-run.json"
        artifact.write_text("{}", encoding="utf-8")
        return _fake_record(
            kwargs["match_id"],
            kwargs["entry"],
            eligible=True,
            artifact_path=str(artifact),
        )

    monkeypatch.setattr(elo_runner, "_run_one_entry", corrected_attempt)
    second = elo_runner.run_elo_gauntlet(
        schedule,
        summary_output_directory=tmp_path,
        retry_ineligible=True,
    )

    record = second.matches[0]
    assert calls == [2]
    assert record.attempt_number == 2
    assert record.eligibility.rating_eligible is True
    assert len(record.prior_attempt_record_paths) == 1
    archived_path = record.prior_attempt_record_paths[0]
    archived = EloMatchRecord.model_validate_json(
        (tmp_path / schedule.matrix_id / "attempts" / record.match_id / "attempt-0001.match.json").read_text(
            encoding="utf-8"
        )
    )
    assert archived_path.endswith("attempt-0001.match.json")
    assert archived.eligibility.rating_eligible is False
    assert any(event.event_type == "ELO_MATCH_RETRY_SCHEDULED" for event in second.events)


def test_retry_refuses_a_schedule_from_another_policy_version(tmp_path) -> None:
    schedule = build_elo_matrix_schedule(
        mode="elo_smoke",
        arena_ids=["standard_skeleton_doors"],
        seeds=[1],
        side_orders=(True,),
    )
    old_entries = [entry.model_copy(update={"policy_version": "old-policy"}) for entry in schedule.entries]
    old_schedule = schedule.model_copy(update={"entries": old_entries})

    with pytest.raises(ValueError, match="different policy identity"):
        elo_runner.run_elo_gauntlet(
            old_schedule,
            summary_output_directory=tmp_path,
            retry_ineligible=True,
        )


def test_no_resume_refuses_to_reuse_an_existing_matrix_workspace(
    monkeypatch: pytest.MonkeyPatch,
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
    elo_runner.run_elo_gauntlet(schedule, summary_output_directory=tmp_path)

    with pytest.raises(ValueError, match="retained evidence"):
        elo_runner.run_elo_gauntlet(
            schedule,
            summary_output_directory=tmp_path,
            resume=False,
        )


def test_match_timeout_is_retained_as_typed_failure_artifact(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    schedule = build_elo_matrix_schedule(
        mode="elo_smoke",
        arena_ids=["standard_skeleton_doors"],
        seeds=[1],
        side_orders=(True,),
    )

    def blocked_selfplay(*_args, **_kwargs):
        time.sleep(1)
        raise AssertionError("deadline did not interrupt the match")

    monkeypatch.setattr(elo_runner, "run_external_selfplay", blocked_selfplay)
    started = time.perf_counter()
    summary = elo_runner.run_elo_gauntlet(
        schedule,
        summary_output_directory=tmp_path,
        resume=False,
        match_timeout_seconds=0.02,
    )
    elapsed = time.perf_counter() - started
    record = summary.matches[0]

    assert elapsed < 0.5
    assert record.eligibility.timed_out is True
    assert record.eligibility.crashed is False
    assert record.eligibility.runner_status == "timeout"
    assert len(record.artifact_paths) == 1
    failure = EloMatchFailureArtifact.model_validate_json(
        open(record.artifact_paths[0], encoding="utf-8").read()
    )
    assert failure.status == "timeout"
    assert failure.match_id == record.match_id
    assert failure.timeout_seconds == 0.02


def test_match_crash_is_retained_as_typed_failure_artifact(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    schedule = build_elo_matrix_schedule(
        mode="elo_smoke",
        arena_ids=["standard_skeleton_doors"],
        seeds=[1],
        side_orders=(True,),
    )

    def crashed_selfplay(*_args, **_kwargs):
        raise ValueError("synthetic evaluator crash")

    monkeypatch.setattr(elo_runner, "run_external_selfplay", crashed_selfplay)
    summary = elo_runner.run_elo_gauntlet(
        schedule,
        summary_output_directory=tmp_path,
        resume=False,
    )
    record = summary.matches[0]
    failure = EloMatchFailureArtifact.model_validate_json(
        open(record.artifact_paths[0], encoding="utf-8").read()
    )

    assert record.eligibility.crashed is True
    assert record.eligibility.timed_out is False
    assert failure.status == "crashed"
    assert failure.exception_type == "ValueError"
    assert "synthetic evaluator crash" in failure.traceback


def _fake_record(
    match_id: str,
    entry,
    *,
    eligible: bool = False,
    artifact_path: str | None = None,
) -> EloMatchRecord:
    base_record = (
        TournamentMatchRecord(
            match_id=match_id,
            arena_id=entry.arena_id,
            random_seed=entry.random_seed,
            hero_first=entry.hero_first,
            status="encounter_ended",
            command_count=1,
            elapsed_ms=1.0,
            outcome="heroes",
            subjectivity_status="passed",
            faction_hp={"heroes": 1, "monsters": 0},
            run_artifact_path=artifact_path,
        )
        if eligible
        else None
    )
    return EloMatchRecord(
        match_id=match_id,
        match_index=entry.match_index,
        runtime_policy_version=POLICY_VERSION if eligible else None,
        runtime_policy_source_hash="test-source-hash" if eligible else None,
        runtime_controller_profile=CONTROLLER_PROFILE if eligible else None,
        runtime_subjectivity_validator=REQUIRED_SUBJECTIVITY_VALIDATOR if eligible else None,
        schedule_entry=entry,
        arena_manifest=_fake_manifest(entry.arena_id) if eligible else None,
        base_record=base_record,
        participants=_fake_participants() if eligible else [],
        eligibility=EloEligibility(
            status="eligible" if eligible else "skipped",
            rating_eligible=eligible,
            reasons=[] if eligible else ["fake"],
            subjectivity_status="passed" if eligible else "not_run",
            runner_status="encounter_ended" if eligible else "fake",
            command_status_counts={},
            encounter_finished=eligible,
            command_cap_reached=False,
            crashed=False,
            timed_out=False,
            has_unknown_outcome=not eligible,
        ),
        artifact_paths=[artifact_path] if artifact_path is not None else [],
        friction_flags=[] if eligible else ["fake"],
    )


def _fake_manifest(arena_id: str) -> ArenaManifest:
    return ArenaManifest(
        arena_id=arena_id,
        title="Test Arena",
        hero_role="test",
        map_size=(1, 1),
        map_bounds=(0, 0, 0, 0),
        roster_hash_by_side={"heroes": "hero", "monsters": "monster"},
        manifest_hash="manifest",
    )


def _fake_participants() -> list[EloParticipant]:
    return [
        EloParticipant(
            participant_id=f"setup_side:{side}",
            ledger="setup_side",
            side=side,
            policy_version=POLICY_VERSION,
            controller_profile=CONTROLLER_PROFILE,
            display_name=side,
        )
        for side in ("heroes", "monsters")
    ]
