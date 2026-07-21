from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

import pytest

from ai.evaluation.config_ladder.artifact_store import (
    atomic_write_json,
    read_gzip_json,
    read_json_model,
    sha256_json,
)
from ai.evaluation.config_ladder.contracts import ConnectedScheduleEntry
from ai.evaluation.config_ladder.worker import execute_worker_task
from ai.evaluation.config_ladder.worker_contracts import (
    MatchWorkerRequest,
    MatchWorkerResponse,
    ProbeOperation,
    ProbeTask,
    WorkerArtifactEnvelope,
    WorkerStatus,
    WorkerTaskMode,
    WorkerTaskResult,
)


_REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def test_fresh_probe_workers_publish_authenticated_gzip_evidence(tmp_path: Path) -> None:
    envelopes: list[WorkerArtifactEnvelope] = []
    responses: list[MatchWorkerResponse] = []

    for attempt_number in (1, 2):
        attempt_dir = tmp_path / f"attempt-{attempt_number}"
        attempt_dir.mkdir()
        request = _probe_request(
            attempt_number=attempt_number,
            dispatch_id=f"dispatch-{attempt_number}",
            canary_token=f"canary-{attempt_number}",
        )
        request_path = attempt_dir / "request.json"
        response_path = attempt_dir / "response.json"
        artifact_path = attempt_dir / "artifact.json.gz"
        request_sha256 = atomic_write_json(request_path, request)

        environment = os.environ.copy()
        environment["PYTHONHASHSEED"] = "0"
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "ai.evaluation.config_ladder.worker",
                "--request",
                str(request_path),
                "--response",
                str(response_path),
                "--artifact",
                str(artifact_path),
                "--parent-pid",
                str(os.getpid()),
            ],
            cwd=_REPOSITORY_ROOT,
            env=environment,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            timeout=10.0,
            check=False,
        )

        assert completed.returncode == 0, completed.stderr.decode("utf-8")
        assert artifact_path.read_bytes().startswith(b"\x1f\x8b")
        response = read_json_model(response_path, MatchWorkerResponse)
        artifact_value, descriptor = read_gzip_json(
            artifact_path,
            expected=response.artifact,
        )
        envelope = WorkerArtifactEnvelope.model_validate(artifact_value)

        assert descriptor == response.artifact
        assert envelope.request_sha256 == request_sha256
        assert envelope.request == request
        assert envelope.worker_pid == response.worker_pid
        assert envelope.parent_pid == os.getpid()
        assert envelope.process_canaries_before == ()
        assert envelope.process_canaries_after == (f"canary-{attempt_number}",)
        assert envelope.result.payload["echo"] == {"attempt": attempt_number}
        assert envelope.result.normalized_result_hash == sha256_json(
            envelope.result.payload
        )
        responses.append(response)
        envelopes.append(envelope)

    assert responses[0].worker_pid != responses[1].worker_pid
    assert all(response.worker_pid != os.getpid() for response in responses)
    assert envelopes[0].process_canaries_after[0] not in envelopes[1].process_canaries_before


def test_worker_soft_timeout_still_publishes_typed_evidence(tmp_path: Path) -> None:
    request = _probe_request(
        attempt_number=1,
        dispatch_id="dispatch-timeout",
        canary_token="soft-timeout-canary",
        operation=ProbeOperation.SLEEP,
        delay_seconds=0.25,
        soft_timeout_seconds=0.05,
    )
    request_path = tmp_path / "request.json"
    response_path = tmp_path / "response.json"
    artifact_path = tmp_path / "artifact.json.gz"
    atomic_write_json(request_path, request)
    environment = os.environ.copy()
    environment["PYTHONHASHSEED"] = "0"

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "ai.evaluation.config_ladder.worker",
            "--request",
            str(request_path),
            "--response",
            str(response_path),
            "--artifact",
            str(artifact_path),
            "--parent-pid",
            str(os.getpid()),
        ],
        cwd=_REPOSITORY_ROOT,
        env=environment,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        timeout=10.0,
        check=False,
    )

    response = read_json_model(response_path, MatchWorkerResponse)
    artifact_value, _ = read_gzip_json(artifact_path, expected=response.artifact)
    envelope = WorkerArtifactEnvelope.model_validate(artifact_value)
    assert completed.returncode == 20
    assert response.status == WorkerStatus.SOFT_TIMEOUT
    assert response.error is not None
    assert response.error.code == "worker_soft_timeout"
    assert envelope.result.status == WorkerStatus.SOFT_TIMEOUT


def test_real_match_callable_seam_enforces_runtime_hash_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PYTHONHASHSEED", "0")
    expected_hashes = {"engine": "engine-hash", "policy": "policy-hash"}
    request = MatchWorkerRequest(
        experiment_id="worker-seam",
        schedule_hash="schedule-hash",
        catalog_hash="catalog-hash",
        entry=_entry(),
        attempt_number=1,
        dispatch_id="dispatch-real",
        mode=WorkerTaskMode.REAL_MATCH,
        expected_runtime_hashes=expected_hashes,
        catalog_snapshot_path="/tmp/catalog.json",
        catalog_snapshot_hash="catalog-snapshot-hash",
    )

    def matching_runner(request: MatchWorkerRequest) -> WorkerTaskResult:
        del request
        return WorkerTaskResult(
            status=WorkerStatus.COMPLETED,
            payload={"runtime_hashes": expected_hashes, "winner": "hero"},
            manifest_hash="manifest-hash",
        )

    result = execute_worker_task(request, real_match_runner=matching_runner)

    assert result.status == WorkerStatus.COMPLETED
    assert result.manifest_hash == "manifest-hash"
    assert result.normalized_result_hash == sha256_json(result.payload)

    def mismatching_runner(request: MatchWorkerRequest) -> WorkerTaskResult:
        del request
        return WorkerTaskResult(
            status=WorkerStatus.COMPLETED,
            payload={"runtime_hashes": {"engine": "different"}},
        )

    mismatch = execute_worker_task(request, real_match_runner=mismatching_runner)
    assert mismatch.status == WorkerStatus.IDENTITY_ERROR
    assert mismatch.error is not None
    assert mismatch.error.code == "runtime_identity_mismatch"


def _probe_request(
    *,
    attempt_number: int,
    dispatch_id: str,
    canary_token: str,
    operation: ProbeOperation = ProbeOperation.ECHO,
    delay_seconds: float = 0.0,
    soft_timeout_seconds: float = 5.0,
) -> MatchWorkerRequest:
    return MatchWorkerRequest(
        experiment_id="isolated-worker-probe",
        schedule_hash="schedule-hash",
        catalog_hash="catalog-hash",
        entry=_entry(),
        attempt_number=attempt_number,
        dispatch_id=dispatch_id,
        mode=WorkerTaskMode.PROBE,
        soft_timeout_seconds=soft_timeout_seconds,
        expected_runtime_hashes={"engine": "engine-hash"},
        probe=ProbeTask(
            operation=operation,
            payload={"attempt": attempt_number},
            delay_seconds=delay_seconds,
            canary_token=canary_token,
        ),
    )


def _entry() -> ConnectedScheduleEntry:
    return ConnectedScheduleEntry(
        schedule_index=0,
        match_id="match-000",
        pair_block_id="pair-000",
        hero_configuration_id="hero.alpha",
        hero_configuration_hash="hero-hash",
        monster_configuration_id="monsters.alpha",
        monster_configuration_hash="monster-hash",
        battlefield_id="field.alpha",
        battlefield_hash="field-hash",
        deployment_id="deployment.alpha",
        deployment_hash="deployment-hash",
        simulation_seed=17,
        opening_treatment="hero_first",
    )
