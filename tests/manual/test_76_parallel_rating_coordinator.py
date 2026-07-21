from __future__ import annotations

import asyncio
import os
from pathlib import Path
import time

import pytest

from ai.evaluation.config_ladder import coordinator as coordinator_module
from ai.evaluation.config_ladder.artifact_store import (
    ExperimentLockUnavailable,
    read_gzip_json,
    read_json_model,
)
from ai.evaluation.config_ladder.contracts import (
    ConnectedRatingSchedule,
    ConnectedScheduleEntry,
)
from ai.evaluation.config_ladder.coordinator import (
    CoordinatorError,
    run_isolated_coordinator,
)
from ai.evaluation.config_ladder.worker_contracts import (
    AttemptOutcome,
    AttemptReceipt,
    CoordinatorCheckpoint,
    MatchWorkerRequest,
    MatchWorkerResponse,
    ProbeOperation,
    ProbeTask,
    RequestFactory,
    WorkerArtifactEnvelope,
    WorkerTaskMode,
)


def test_parallel_coordinator_commits_in_schedule_order_and_resumes(
    tmp_path: Path,
) -> None:
    schedule = _schedule("parallel-order", 4)
    output_root = tmp_path / "canonical"
    spool_root = tmp_path / "private-spool"
    factory = _probe_factory(
        schedule,
        delays={0: 1.0, 1: 0.0, 2: 0.25, 3: 0.0},
    )

    first = asyncio.run(
        run_isolated_coordinator(
            schedule,
            output_root=output_root,
            spool_root=spool_root,
            request_factory=factory,
            worker_count=2,
            hard_timeout_seconds=10.0,
            max_infrastructure_attempts=1,
        )
    )

    assert first.committed_order == (0, 1, 2, 3)
    assert [record.entry.schedule_index for record in first.records] == [0, 1, 2, 3]
    assert all(record.outcome == AttemptOutcome.COMPLETED for record in first.records)
    assert first.spawned_worker_count == 4
    assert first.max_active_workers == 2
    worker_pids = {record.worker_pid for record in first.records}
    assert None not in worker_pids
    assert len(worker_pids) == 4

    experiment_dir = output_root / schedule.experiment_id
    responses_by_index: dict[int, MatchWorkerResponse] = {}
    for record in first.records:
        receipt = read_json_model(
            experiment_dir / record.receipt_path,
            AttemptReceipt,
        )
        assert receipt.artifact is not None
        assert receipt.artifact_path is not None
        artifact_value, descriptor = read_gzip_json(
            experiment_dir / receipt.artifact_path,
            expected=receipt.artifact,
        )
        envelope = WorkerArtifactEnvelope.model_validate(artifact_value)
        assert descriptor == receipt.artifact
        assert envelope.process_canaries_before == ()
        assert envelope.process_canaries_after == (
            f"row-{record.entry.schedule_index}-attempt-1",
        )
        assert receipt.response_path is not None
        responses_by_index[record.entry.schedule_index] = read_json_model(
            experiment_dir / receipt.response_path,
            MatchWorkerResponse,
        )

    # Row 1 finishes first, but row 0 remains the first canonical commit.
    assert responses_by_index[1].completed_at < responses_by_index[0].completed_at
    checkpoint = read_json_model(
        experiment_dir / "checkpoint.json",
        CoordinatorCheckpoint,
    )
    assert checkpoint.completed_schedule_indices == (0, 1, 2, 3)
    assert checkpoint.next_commit_index == 4

    resumed = asyncio.run(
        run_isolated_coordinator(
            schedule,
            output_root=output_root,
            spool_root=spool_root,
            request_factory=factory,
            worker_count=3,
            hard_timeout_seconds=10.0,
            max_infrastructure_attempts=1,
        )
    )
    assert resumed.records == first.records
    assert resumed.committed_order == ()
    assert resumed.spawned_worker_count == 0
    assert resumed.resumed_record_count == 4

    artifact_relative_path = first.records[0].artifact_path
    assert artifact_relative_path is not None
    artifact_path = experiment_dir / artifact_relative_path
    artifact_bytes = artifact_path.read_bytes()
    artifact_path.write_bytes(artifact_bytes[:-1] + bytes([artifact_bytes[-1] ^ 0xFF]))
    with pytest.raises(CoordinatorError):
        asyncio.run(
            run_isolated_coordinator(
                schedule,
                output_root=output_root,
                spool_root=spool_root,
                request_factory=factory,
                worker_count=1,
                max_infrastructure_attempts=1,
            )
        )


def test_crashed_attempts_use_fresh_processes_and_stop_at_retry_budget(
    tmp_path: Path,
) -> None:
    schedule = _schedule("crash-retry", 1)
    output_root = tmp_path / "canonical"
    spool_root = tmp_path / "private-spool"
    factory = _probe_factory(
        schedule,
        operations={0: ProbeOperation.CRASH},
    )

    summary = asyncio.run(
        run_isolated_coordinator(
            schedule,
            output_root=output_root,
            spool_root=spool_root,
            request_factory=factory,
            worker_count=1,
            hard_timeout_seconds=10.0,
            max_infrastructure_attempts=2,
        )
    )

    assert summary.spawned_worker_count == 2
    assert summary.records[0].outcome == AttemptOutcome.WORKER_CRASH
    receipts = [
        read_json_model(path, AttemptReceipt)
        for path in sorted(
            (output_root / schedule.experiment_id / "attempts").glob(
                "*/attempt-*/receipt.json"
            )
        )
    ]
    assert [receipt.attempt_number for receipt in receipts] == [1, 2]
    assert len({receipt.worker_pid for receipt in receipts}) == 2
    assert all(receipt.retryable for receipt in receipts)


def test_resume_recovers_a_complete_private_spool_without_respawning(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    schedule = _schedule("spool-recovery", 1)
    output_root = tmp_path / "canonical"
    spool_root = tmp_path / "private-spool"
    factory = _probe_factory(schedule)

    def interrupt_before_promotion(*args: object, **kwargs: object) -> object:
        del args, kwargs
        raise RuntimeError("simulated coordinator interruption")

    original_publish = coordinator_module._publish_attempt
    monkeypatch.setattr(
        coordinator_module,
        "_publish_attempt",
        interrupt_before_promotion,
    )
    with pytest.raises(RuntimeError, match="simulated coordinator interruption"):
        asyncio.run(
            run_isolated_coordinator(
                schedule,
                output_root=output_root,
                spool_root=spool_root,
                request_factory=factory,
                worker_count=1,
                hard_timeout_seconds=10.0,
                max_infrastructure_attempts=1,
            )
        )
    assert list(spool_root.glob("*/attempts/*/attempt-*/response.json"))

    monkeypatch.setattr(coordinator_module, "_publish_attempt", original_publish)
    resumed = asyncio.run(
        run_isolated_coordinator(
            schedule,
            output_root=output_root,
            spool_root=spool_root,
            request_factory=factory,
            worker_count=1,
            hard_timeout_seconds=10.0,
            max_infrastructure_attempts=1,
        )
    )

    assert resumed.spawned_worker_count == 0
    assert resumed.committed_order == (0,)
    assert resumed.records[0].outcome == AttemptOutcome.COMPLETED
    assert not list(spool_root.glob("*/attempts/*/attempt-*/request.json"))


def test_hard_timeout_terminates_the_entire_worker_process_group(
    tmp_path: Path,
) -> None:
    schedule = _schedule("process-group-timeout", 1)
    output_root = tmp_path / "canonical"
    spool_root = tmp_path / "private-spool"
    factory = _probe_factory(
        schedule,
        operations={0: ProbeOperation.SPAWN_CHILD_AND_SLEEP},
        child_sleep_seconds=30.0,
        soft_timeout_seconds=20.0,
    )

    summary = asyncio.run(
        run_isolated_coordinator(
            schedule,
            output_root=output_root,
            spool_root=spool_root,
            request_factory=factory,
            worker_count=1,
            hard_timeout_seconds=8.0,
            terminate_grace_seconds=0.4,
            max_infrastructure_attempts=1,
        )
    )

    assert summary.spawned_worker_count == 1
    assert summary.records[0].outcome == AttemptOutcome.HARD_TIMEOUT
    experiment_dir = output_root / schedule.experiment_id
    receipt = read_json_model(
        experiment_dir / summary.records[0].receipt_path,
        AttemptReceipt,
    )
    assert receipt.hard_timed_out
    assert receipt.process_group_id == receipt.worker_pid
    stdout = (experiment_dir / receipt.stdout_path).read_text("utf-8")
    child_pid = int(stdout.strip().removeprefix("CHILD_PID="))

    deadline = time.monotonic() + 2.0
    while _pid_exists(child_pid) and time.monotonic() < deadline:
        time.sleep(0.025)
    assert not _pid_exists(child_pid)
    assert receipt.process_group_id is not None
    assert not _process_group_exists(receipt.process_group_id)


def test_experiment_fcntl_lock_rejects_a_second_coordinator(
    tmp_path: Path,
) -> None:
    async def exercise() -> None:
        schedule = _schedule("exclusive-lock", 1)
        output_root = tmp_path / "canonical"
        spool_root = tmp_path / "private-spool"
        factory = _probe_factory(schedule, delays={0: 0.6})
        first = asyncio.create_task(
            run_isolated_coordinator(
                schedule,
                output_root=output_root,
                spool_root=spool_root,
                request_factory=factory,
                worker_count=1,
                    hard_timeout_seconds=10.0,
                max_infrastructure_attempts=1,
            )
        )
        for _ in range(100):
            if list(spool_root.glob("*/attempts/*/attempt-*/request.json")):
                break
            await asyncio.sleep(0.01)
        with pytest.raises(ExperimentLockUnavailable):
            await run_isolated_coordinator(
                schedule,
                output_root=output_root,
                spool_root=spool_root,
                request_factory=factory,
                worker_count=1,
                    hard_timeout_seconds=10.0,
                max_infrastructure_attempts=1,
            )
        result = await first
        assert result.records[0].outcome == AttemptOutcome.COMPLETED

    asyncio.run(exercise())


def _probe_factory(
    schedule: ConnectedRatingSchedule,
    *,
    delays: dict[int, float] | None = None,
    operations: dict[int, ProbeOperation] | None = None,
    child_sleep_seconds: float = 30.0,
    soft_timeout_seconds: float = 5.0,
) -> RequestFactory:
    delays = dict(delays or {})
    operations = dict(operations or {})

    def build(
        entry: ConnectedScheduleEntry,
        attempt_number: int,
        dispatch_id: str,
    ) -> MatchWorkerRequest:
        return MatchWorkerRequest(
            experiment_id=schedule.experiment_id,
            schedule_hash=schedule.schedule_hash,
            catalog_hash=schedule.catalog_hash,
            entry=entry,
            attempt_number=attempt_number,
            dispatch_id=dispatch_id,
            mode=WorkerTaskMode.PROBE,
            soft_timeout_seconds=soft_timeout_seconds,
            expected_runtime_hashes={
                "hero_configuration": entry.hero_configuration_hash,
                "monster_configuration": entry.monster_configuration_hash,
                "battlefield": entry.battlefield_hash,
                "deployment": entry.deployment_hash,
            },
            probe=ProbeTask(
                operation=operations.get(entry.schedule_index, ProbeOperation.ECHO),
                payload={"schedule_index": entry.schedule_index},
                delay_seconds=delays.get(entry.schedule_index, 0.0),
                child_sleep_seconds=child_sleep_seconds,
                canary_token=f"row-{entry.schedule_index}-attempt-{attempt_number}",
            ),
        )

    return build


def _schedule(experiment_id: str, count: int) -> ConnectedRatingSchedule:
    entries = tuple(
        ConnectedScheduleEntry(
            schedule_index=index,
            match_id=f"match-{index:03d}",
            pair_block_id=f"pair-{index // 2:03d}",
            hero_configuration_id=f"hero.{index}",
            hero_configuration_hash=f"hero-hash-{index}",
            monster_configuration_id=f"monsters.{index}",
            monster_configuration_hash=f"monster-hash-{index}",
            battlefield_id="field.alpha",
            battlefield_hash="field-hash",
            deployment_id="deployment.alpha",
            deployment_hash="deployment-hash",
            simulation_seed=1000 + index,
            opening_treatment="hero_first" if index % 2 == 0 else "monster_first",
        )
        for index in range(count)
    )
    return ConnectedRatingSchedule(
        experiment_id=experiment_id,
        created_at="2026-01-01T00:00:00+00:00",
        catalog_hash=f"catalog-{experiment_id}",
        entries=entries,
        schedule_hash=f"schedule-{experiment_id}",
    )


def _pid_exists(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


def _process_group_exists(process_group_id: int) -> bool:
    try:
        os.killpg(process_group_id, 0)
    except ProcessLookupError:
        return False
    return True
