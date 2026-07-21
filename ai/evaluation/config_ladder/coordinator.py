"""Bounded coordinator for disposable configuration-ladder worker processes."""

from __future__ import annotations

import argparse
import asyncio
from collections import deque
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import signal
import sys
import time
import traceback as traceback_module
from pydantic import ValidationError

from ai.evaluation.config_ladder.artifact_store import (
    ArtifactValidationError,
    ExperimentLock,
    atomic_write_bytes,
    atomic_write_json,
    promote_file_atomic,
    read_gzip_json,
    read_json_model,
    reproducible_result_hash,
    safe_path_component,
    sha256_bytes,
    sha256_file,
    sha256_json,
)
from ai.evaluation.config_ladder.contracts import (
    ConnectedRatingSchedule,
    ConnectedScheduleEntry,
)
from ai.evaluation.config_ladder.worker_contracts import (
    ArtifactDescriptor,
    AttemptOutcome,
    AttemptReceipt,
    CanonicalMatchRecord,
    CoordinatorCheckpoint,
    CoordinatorSummary,
    MatchWorkerRequest,
    MatchWorkerResponse,
    ProbeOperation,
    ProbeTask,
    RequestFactory,
    WorkerArtifactEnvelope,
    WorkerError,
    WorkerStatus,
    WorkerTaskMode,
)


_WORKER_MODULE = "ai.evaluation.config_ladder.worker"
_EXPECTED_EXIT_CODES = {
    WorkerStatus.COMPLETED: 0,
    WorkerStatus.SOFT_TIMEOUT: 20,
    WorkerStatus.TASK_ERROR: 21,
    WorkerStatus.IDENTITY_ERROR: 22,
    WorkerStatus.UNSUPPORTED: 23,
}
_RETRYABLE_OUTCOMES = {
    AttemptOutcome.HARD_TIMEOUT,
    AttemptOutcome.WORKER_CRASH,
    AttemptOutcome.PROTOCOL_ERROR,
    AttemptOutcome.ARTIFACT_VALIDATION_ERROR,
    AttemptOutcome.PROCESS_LEAK,
    AttemptOutcome.SPAWN_ERROR,
    AttemptOutcome.INTERRUPTED,
}


class CoordinatorError(RuntimeError):
    """Raised for invalid schedules, requests, or durable coordinator state."""


class WorkerProtocolError(RuntimeError):
    """Raised when a worker response cannot be bound to its dispatch."""


@dataclass(frozen=True)
class _AttemptPaths:
    spool_dir: Path
    spool_request: Path
    spool_response: Path
    spool_artifact: Path
    spool_stdout: Path
    spool_stderr: Path
    canonical_dir: Path
    canonical_request: Path
    canonical_response: Path
    canonical_artifact: Path
    canonical_stdout: Path
    canonical_stderr: Path
    canonical_receipt: Path


@dataclass(frozen=True)
class _AuthenticatedOutput:
    response: MatchWorkerResponse
    artifact: ArtifactDescriptor


@dataclass(frozen=True)
class _AttemptExecution:
    receipt: AttemptReceipt
    receipt_relative_path: str
    spawned_worker: bool


@dataclass(frozen=True)
class _PendingAttempt:
    entry: ConnectedScheduleEntry
    attempt_number: int


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _make_error(code: str, exc: BaseException, *, with_traceback: bool = True) -> WorkerError:
    formatted = traceback_module.format_exc() if with_traceback else None
    if formatted == "NoneType: None\n":
        formatted = None
    return WorkerError(
        code=code,
        exception_type=type(exc).__name__,
        message=str(exc),
        traceback=formatted,
    )


def _validate_schedule(schedule: ConnectedRatingSchedule) -> None:
    expected_indices = list(range(len(schedule.entries)))
    observed_indices = [entry.schedule_index for entry in schedule.entries]
    if observed_indices != expected_indices:
        raise CoordinatorError(
            "Schedule entries must be ordered with contiguous zero-based schedule_index values."
        )
    match_ids = [entry.match_id for entry in schedule.entries]
    if len(match_ids) != len(set(match_ids)):
        raise CoordinatorError("Schedule match_id values must be unique.")
    safe_path_component(schedule.experiment_id)
    for entry in schedule.entries:
        safe_path_component(entry.match_id)


def _dispatch_id(schedule_hash: str, schedule_index: int, attempt_number: int) -> str:
    identity_hash = sha256_json(
        {
            "schedule_hash": schedule_hash,
            "schedule_index": schedule_index,
            "attempt_number": attempt_number,
        }
    )
    return f"dispatch-{identity_hash[:20]}"


def _attempt_stem(entry: ConnectedScheduleEntry) -> str:
    return f"{entry.schedule_index:08d}-{safe_path_component(entry.match_id)}"


def _attempt_paths(
    experiment_dir: Path,
    spool_experiment_dir: Path,
    entry: ConnectedScheduleEntry,
    attempt_number: int,
    dispatch_id: str,
) -> _AttemptPaths:
    attempt_name = f"attempt-{attempt_number:04d}-{safe_path_component(dispatch_id)}"
    stem = _attempt_stem(entry)
    spool_dir = spool_experiment_dir / "attempts" / stem / attempt_name
    canonical_dir = experiment_dir / "attempts" / stem / attempt_name
    return _AttemptPaths(
        spool_dir=spool_dir,
        spool_request=spool_dir / "request.json",
        spool_response=spool_dir / "response.json",
        spool_artifact=spool_dir / "artifact.json.gz",
        spool_stdout=spool_dir / "stdout.log",
        spool_stderr=spool_dir / "stderr.log",
        canonical_dir=canonical_dir,
        canonical_request=canonical_dir / "request.json",
        canonical_response=canonical_dir / "response.json",
        canonical_artifact=canonical_dir / "artifact.json.gz",
        canonical_stdout=canonical_dir / "stdout.log",
        canonical_stderr=canonical_dir / "stderr.log",
        canonical_receipt=canonical_dir / "receipt.json",
    )


def _relative_path(experiment_dir: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(experiment_dir.resolve()).as_posix()
    except ValueError as exc:
        raise CoordinatorError(f"Canonical path escapes experiment root: {path}") from exc


def _resolve_canonical_path(experiment_dir: Path, relative_path: str) -> Path:
    candidate = (experiment_dir / relative_path).resolve()
    if not candidate.is_relative_to(experiment_dir.resolve()):
        raise CoordinatorError(f"Receipt path escapes experiment root: {relative_path!r}")
    return candidate


def _validate_request(
    request: MatchWorkerRequest,
    schedule: ConnectedRatingSchedule,
    entry: ConnectedScheduleEntry,
    attempt_number: int,
    dispatch_id: str,
) -> None:
    mismatches: list[str] = []
    if request.experiment_id != schedule.experiment_id:
        mismatches.append("experiment_id")
    if request.schedule_hash != schedule.schedule_hash:
        mismatches.append("schedule_hash")
    if request.catalog_hash != schedule.catalog_hash:
        mismatches.append("catalog_hash")
    if request.entry != entry:
        mismatches.append("entry")
    if request.attempt_number != attempt_number:
        mismatches.append("attempt_number")
    if request.dispatch_id != dispatch_id:
        mismatches.append("dispatch_id")
    if mismatches:
        raise CoordinatorError(
            f"Request factory violated immutable dispatch fields: {', '.join(mismatches)}"
        )


def _authenticate_worker_output(
    request: MatchWorkerRequest,
    request_sha256: str,
    response_path: Path,
    artifact_path: Path,
    *,
    expected_worker_pid: int | None,
    expected_parent_pid: int | None,
    expected_returncode: int | None,
    max_artifact_payload_bytes: int,
) -> _AuthenticatedOutput:
    try:
        response = read_json_model(response_path, MatchWorkerResponse)
    except (OSError, ValidationError, ValueError) as exc:
        raise WorkerProtocolError("Worker response is missing or invalid.") from exc

    expected_echoes = {
        "experiment_id": request.experiment_id,
        "schedule_hash": request.schedule_hash,
        "match_id": request.entry.match_id,
        "schedule_index": request.entry.schedule_index,
        "attempt_number": request.attempt_number,
        "dispatch_id": request.dispatch_id,
        "request_sha256": request_sha256,
    }
    observed_echoes = {
        "experiment_id": response.experiment_id,
        "schedule_hash": response.schedule_hash,
        "match_id": response.match_id,
        "schedule_index": response.schedule_index,
        "attempt_number": response.attempt_number,
        "dispatch_id": response.dispatch_id,
        "request_sha256": response.request_sha256,
    }
    if observed_echoes != expected_echoes:
        raise WorkerProtocolError("Worker response identity does not match its request.")
    if expected_worker_pid is not None and response.worker_pid != expected_worker_pid:
        raise WorkerProtocolError("Worker response PID does not match the spawned process.")
    if expected_parent_pid is not None and response.parent_pid != expected_parent_pid:
        raise WorkerProtocolError("Worker response parent PID does not match the coordinator.")
    if expected_returncode is not None:
        expected_code = _EXPECTED_EXIT_CODES[response.status]
        if expected_returncode != expected_code:
            raise WorkerProtocolError(
                f"Worker exit code {expected_returncode} disagrees with status {response.status.value}."
            )
    if response.artifact is None:
        raise ArtifactValidationError("Worker response did not publish an artifact descriptor.")
    if not artifact_path.is_file():
        raise ArtifactValidationError("Worker response artifact is missing.")

    artifact_value, descriptor = read_gzip_json(
        artifact_path,
        expected=response.artifact,
        max_payload_bytes=max_artifact_payload_bytes,
    )
    try:
        envelope = WorkerArtifactEnvelope.model_validate(artifact_value)
    except ValidationError as exc:
        raise ArtifactValidationError("Worker artifact envelope is invalid.") from exc
    if envelope.request_sha256 != request_sha256 or envelope.request != request:
        raise ArtifactValidationError("Worker artifact is not bound to the exact request.")
    if envelope.worker_pid != response.worker_pid or envelope.parent_pid != response.parent_pid:
        raise ArtifactValidationError("Worker artifact process identity differs from its response.")
    if envelope.observed_python_hash_seed != request.python_hash_seed:
        raise ArtifactValidationError("Worker artifact observed the wrong PYTHONHASHSEED.")
    if envelope.process_canaries_before:
        raise ArtifactValidationError(
            "Worker process-local canaries were non-empty before task execution."
        )
    probe = request.probe
    if probe is not None and probe.canary_token is not None:
        if probe.canary_token not in envelope.process_canaries_after:
            raise ArtifactValidationError("Worker did not retain its task-local leakage canary.")

    result = envelope.result
    if result.status != response.status:
        raise ArtifactValidationError("Artifact result status differs from worker response.")
    if result.manifest_hash != response.manifest_hash:
        raise ArtifactValidationError("Artifact manifest hash differs from worker response.")
    if result.normalized_result_hash != response.normalized_result_hash:
        raise ArtifactValidationError("Artifact normalized hash differs from worker response.")
    if result.subjectivity_status != response.subjectivity_status:
        raise ArtifactValidationError("Artifact subjectivity status differs from worker response.")
    if result.subjectivity_violation_count != response.subjectivity_violation_count:
        raise ArtifactValidationError("Artifact subjectivity count differs from worker response.")
    if result.error != response.error:
        raise ArtifactValidationError("Artifact error differs from worker response.")
    if result.normalized_result_hash != reproducible_result_hash(result.payload):
        raise ArtifactValidationError("Worker normalized result hash is not reproducible.")
    if request.mode == WorkerTaskMode.PROBE:
        if result.payload.get("worker_pid") != response.worker_pid:
            raise ArtifactValidationError("Probe payload worker PID is inconsistent.")
        if result.payload.get("parent_pid") != response.parent_pid:
            raise ArtifactValidationError("Probe payload parent PID is inconsistent.")
    return _AuthenticatedOutput(response=response, artifact=descriptor)


def _outcome_for_status(status: WorkerStatus) -> AttemptOutcome:
    return AttemptOutcome(status.value)


def _publish_attempt(
    experiment_dir: Path,
    paths: _AttemptPaths,
    request: MatchWorkerRequest,
    request_sha256: str,
    *,
    outcome: AttemptOutcome,
    elapsed_ms: float,
    process_group_id: int | None,
    process_returncode: int | None,
    hard_timed_out: bool,
    spawned_worker_pid: int | None,
    authenticated: _AuthenticatedOutput | None,
    error: WorkerError | None,
) -> tuple[AttemptReceipt, str]:
    if not paths.spool_stdout.exists():
        atomic_write_bytes(paths.spool_stdout, b"", immutable=True)
    if not paths.spool_stderr.exists():
        atomic_write_bytes(paths.spool_stderr, b"", immutable=True)

    promote_file_atomic(
        paths.spool_request,
        paths.canonical_request,
        expected_sha256=request_sha256,
    )
    stdout_sha256 = sha256_file(paths.spool_stdout)
    stdout_size_bytes = paths.spool_stdout.stat().st_size
    stderr_sha256 = sha256_file(paths.spool_stderr)
    stderr_size_bytes = paths.spool_stderr.stat().st_size
    promote_file_atomic(
        paths.spool_stdout,
        paths.canonical_stdout,
        expected_sha256=stdout_sha256,
    )
    promote_file_atomic(
        paths.spool_stderr,
        paths.canonical_stderr,
        expected_sha256=stderr_sha256,
    )

    response_sha256: str | None = None
    response_relative: str | None = None
    if paths.spool_response.is_file():
        response_sha256 = sha256_file(paths.spool_response)
        promote_file_atomic(
            paths.spool_response,
            paths.canonical_response,
            expected_sha256=response_sha256,
        )
        response_relative = _relative_path(experiment_dir, paths.canonical_response)

    artifact_relative: str | None = None
    artifact_file_sha256: str | None = None
    artifact_file_size_bytes: int | None = None
    if paths.spool_artifact.is_file():
        artifact_file_sha256 = sha256_file(paths.spool_artifact)
        artifact_file_size_bytes = paths.spool_artifact.stat().st_size
        promote_file_atomic(
            paths.spool_artifact,
            paths.canonical_artifact,
            expected_sha256=artifact_file_sha256,
        )
        artifact_relative = _relative_path(experiment_dir, paths.canonical_artifact)

    response = authenticated.response if authenticated is not None else None
    receipt = AttemptReceipt(
        entry=request.entry,
        attempt_number=request.attempt_number,
        dispatch_id=request.dispatch_id,
        outcome=outcome,
        retryable=outcome in _RETRYABLE_OUTCOMES,
        worker_status=response.status if response is not None else None,
        worker_pid=response.worker_pid if response is not None else spawned_worker_pid,
        process_group_id=process_group_id,
        process_returncode=process_returncode,
        hard_timed_out=hard_timed_out,
        elapsed_ms=elapsed_ms,
        request_sha256=request_sha256,
        response_sha256=response_sha256,
        artifact=authenticated.artifact if authenticated is not None else None,
        artifact_file_sha256=artifact_file_sha256,
        artifact_file_size_bytes=artifact_file_size_bytes,
        normalized_result_hash=(
            response.normalized_result_hash if response is not None else None
        ),
        subjectivity_status=response.subjectivity_status if response is not None else "not_run",
        subjectivity_violation_count=(
            response.subjectivity_violation_count if response is not None else 0
        ),
        request_path=_relative_path(experiment_dir, paths.canonical_request),
        response_path=response_relative,
        artifact_path=artifact_relative,
        stdout_path=_relative_path(experiment_dir, paths.canonical_stdout),
        stdout_sha256=stdout_sha256,
        stdout_size_bytes=stdout_size_bytes,
        stderr_path=_relative_path(experiment_dir, paths.canonical_stderr),
        stderr_sha256=stderr_sha256,
        stderr_size_bytes=stderr_size_bytes,
        error=error if error is not None else (response.error if response is not None else None),
    )
    atomic_write_json(paths.canonical_receipt, receipt, immutable=True)
    shutil.rmtree(paths.spool_dir, ignore_errors=True)
    return receipt, _relative_path(experiment_dir, paths.canonical_receipt)


def _process_group_exists(process_group_id: int) -> bool:
    try:
        os.killpg(process_group_id, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _signal_process_group(process_group_id: int, signal_number: int) -> None:
    try:
        os.killpg(process_group_id, signal_number)
    except ProcessLookupError:
        return


async def _wait_for_process_group_exit(process_group_id: int, timeout: float) -> bool:
    deadline = time.monotonic() + timeout
    while _process_group_exists(process_group_id):
        if time.monotonic() >= deadline:
            return False
        await asyncio.sleep(0.025)
    return True


async def _terminate_process_group(
    process: asyncio.subprocess.Process,
    process_group_id: int,
    grace_seconds: float,
) -> bool:
    _signal_process_group(process_group_id, signal.SIGTERM)
    try:
        await asyncio.wait_for(asyncio.shield(process.wait()), timeout=grace_seconds)
    except asyncio.TimeoutError:
        pass
    group_gone = await _wait_for_process_group_exit(process_group_id, grace_seconds)
    if not group_gone:
        _signal_process_group(process_group_id, signal.SIGKILL)
        if process.returncode is None:
            try:
                await asyncio.wait_for(
                    asyncio.shield(process.wait()),
                    timeout=grace_seconds,
                )
            except asyncio.TimeoutError:
                pass
        group_gone = await _wait_for_process_group_exit(process_group_id, grace_seconds)
    if process.returncode is None:
        await process.wait()
    return group_gone


async def _execute_attempt(
    schedule: ConnectedRatingSchedule,
    experiment_dir: Path,
    spool_experiment_dir: Path,
    pending: _PendingAttempt,
    request_factory: RequestFactory,
    *,
    worker_python: str,
    worker_module: str,
    worker_cwd: Path,
    hard_timeout_seconds: float,
    terminate_grace_seconds: float,
    max_artifact_payload_bytes: int,
) -> _AttemptExecution:
    entry = pending.entry
    attempt_number = pending.attempt_number
    dispatch_id = _dispatch_id(schedule.schedule_hash, entry.schedule_index, attempt_number)
    request = MatchWorkerRequest.model_validate(
        request_factory(entry, attempt_number, dispatch_id)
    )
    _validate_request(request, schedule, entry, attempt_number, dispatch_id)
    paths = _attempt_paths(
        experiment_dir,
        spool_experiment_dir,
        entry,
        attempt_number,
        dispatch_id,
    )
    try:
        paths.spool_dir.mkdir(parents=True, exist_ok=False)
    except FileExistsError as exc:
        raise CoordinatorError(
            f"Unrecovered spool attempt already exists: {paths.spool_dir}"
        ) from exc
    request_sha256 = atomic_write_json(paths.spool_request, request, immutable=True)
    atomic_write_bytes(paths.spool_stdout, b"", immutable=True)
    atomic_write_bytes(paths.spool_stderr, b"", immutable=True)

    environment = os.environ.copy()
    environment["PYTHONHASHSEED"] = request.python_hash_seed
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment["DND_ISOLATED_MATCH_WORKER"] = "1"
    environment.pop("PYTHONINSPECT", None)
    environment.pop("PYTHONSTARTUP", None)

    process: asyncio.subprocess.Process | None = None
    stdout_stream = paths.spool_stdout.open("wb")
    stderr_stream = paths.spool_stderr.open("wb")
    attempt_started = time.monotonic()
    try:
        try:
            process = await asyncio.create_subprocess_exec(
                worker_python,
                "-m",
                worker_module,
                "--request",
                str(paths.spool_request),
                "--response",
                str(paths.spool_response),
                "--artifact",
                str(paths.spool_artifact),
                "--parent-pid",
                str(os.getpid()),
                cwd=str(worker_cwd),
                env=environment,
                stdin=asyncio.subprocess.DEVNULL,
                stdout=stdout_stream,
                stderr=stderr_stream,
                start_new_session=True,
            )
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            elapsed_ms = (time.monotonic() - attempt_started) * 1000.0
            stdout_stream.close()
            stderr_stream.close()
            error = _make_error("worker_spawn_error", exc)
            receipt, receipt_path = await asyncio.to_thread(
                _publish_attempt,
                experiment_dir,
                paths,
                request,
                request_sha256,
                outcome=AttemptOutcome.SPAWN_ERROR,
                elapsed_ms=elapsed_ms,
                process_group_id=None,
                process_returncode=None,
                hard_timed_out=False,
                spawned_worker_pid=None,
                authenticated=None,
                error=error,
            )
            return _AttemptExecution(receipt, receipt_path, spawned_worker=False)
        finally:
            if not stdout_stream.closed:
                stdout_stream.close()
            if not stderr_stream.closed:
                stderr_stream.close()

        process_group_id = process.pid
        hard_timed_out = False
        leak_detected = False
        try:
            await asyncio.wait_for(
                asyncio.shield(process.wait()),
                timeout=hard_timeout_seconds,
            )
        except asyncio.TimeoutError:
            hard_timed_out = True
            group_gone = await _terminate_process_group(
                process,
                process_group_id,
                terminate_grace_seconds,
            )
            leak_detected = not group_gone
        except asyncio.CancelledError:
            await asyncio.shield(
                _terminate_process_group(
                    process,
                    process_group_id,
                    terminate_grace_seconds,
                )
            )
            raise

        if not hard_timed_out and _process_group_exists(process_group_id):
            leak_detected = True
            await _terminate_process_group(
                process,
                process_group_id,
                terminate_grace_seconds,
            )
        elapsed_ms = (time.monotonic() - attempt_started) * 1000.0

        authenticated: _AuthenticatedOutput | None = None
        error: WorkerError | None = None
        if leak_detected:
            outcome = AttemptOutcome.PROCESS_LEAK
            error = _make_error(
                "worker_process_group_leak",
                RuntimeError(f"Process group {process_group_id} survived worker completion."),
                with_traceback=False,
            )
        elif hard_timed_out:
            outcome = AttemptOutcome.HARD_TIMEOUT
            error = _make_error(
                "coordinator_hard_timeout",
                TimeoutError(
                    f"Hard timeout expired after {hard_timeout_seconds:.3f}s."
                ),
                with_traceback=False,
            )
        elif not paths.spool_response.is_file():
            outcome = AttemptOutcome.WORKER_CRASH
            error = _make_error(
                "worker_response_missing",
                RuntimeError(
                    f"Worker exited with {process.returncode} without a response."
                ),
                with_traceback=False,
            )
        else:
            try:
                authenticated = await asyncio.to_thread(
                    _authenticate_worker_output,
                    request,
                    request_sha256,
                    paths.spool_response,
                    paths.spool_artifact,
                    expected_worker_pid=process.pid,
                    expected_parent_pid=os.getpid(),
                    expected_returncode=process.returncode,
                    max_artifact_payload_bytes=max_artifact_payload_bytes,
                )
                outcome = _outcome_for_status(authenticated.response.status)
            except WorkerProtocolError as exc:
                outcome = AttemptOutcome.PROTOCOL_ERROR
                error = _make_error("worker_protocol_error", exc)
            except (ArtifactValidationError, OSError) as exc:
                outcome = AttemptOutcome.ARTIFACT_VALIDATION_ERROR
                error = _make_error("worker_artifact_validation_error", exc)

        receipt, receipt_path = await asyncio.to_thread(
            _publish_attempt,
            experiment_dir,
            paths,
            request,
            request_sha256,
            outcome=outcome,
            elapsed_ms=elapsed_ms,
            process_group_id=process_group_id,
            process_returncode=process.returncode,
            hard_timed_out=hard_timed_out,
            spawned_worker_pid=process.pid,
            authenticated=authenticated,
            error=error,
        )
        return _AttemptExecution(receipt, receipt_path, spawned_worker=True)
    finally:
        if process is not None and process.returncode is None:
            await _terminate_process_group(
                process,
                process.pid,
                terminate_grace_seconds,
            )


def _recover_spool_attempts(
    schedule: ConnectedRatingSchedule,
    experiment_dir: Path,
    spool_experiment_dir: Path,
    *,
    max_artifact_payload_bytes: int,
) -> None:
    if not spool_experiment_dir.exists():
        return
    entries_by_index = {entry.schedule_index: entry for entry in schedule.entries}
    for request_path in sorted(spool_experiment_dir.glob("attempts/*/attempt-*/request.json")):
        request = read_json_model(request_path, MatchWorkerRequest)
        entry = entries_by_index.get(request.entry.schedule_index)
        if entry is None:
            raise CoordinatorError(f"Spool request references unknown schedule row: {request_path}")
        expected_dispatch = _dispatch_id(
            schedule.schedule_hash,
            entry.schedule_index,
            request.attempt_number,
        )
        _validate_request(
            request,
            schedule,
            entry,
            request.attempt_number,
            expected_dispatch,
        )
        paths = _attempt_paths(
            experiment_dir,
            spool_experiment_dir,
            entry,
            request.attempt_number,
            request.dispatch_id,
        )
        if request_path.parent.resolve() != paths.spool_dir.resolve():
            raise CoordinatorError(f"Spool request is stored under the wrong identity path: {request_path}")
        if paths.canonical_receipt.exists():
            continue
        request_sha256 = sha256_file(request_path)
        authenticated: _AuthenticatedOutput | None = None
        error: WorkerError | None = None
        if paths.spool_response.is_file():
            try:
                authenticated = _authenticate_worker_output(
                    request,
                    request_sha256,
                    paths.spool_response,
                    paths.spool_artifact,
                    expected_worker_pid=None,
                    expected_parent_pid=None,
                    expected_returncode=None,
                    max_artifact_payload_bytes=max_artifact_payload_bytes,
                )
                outcome = _outcome_for_status(authenticated.response.status)
            except WorkerProtocolError as exc:
                outcome = AttemptOutcome.PROTOCOL_ERROR
                error = _make_error("recovered_worker_protocol_error", exc)
            except (ArtifactValidationError, OSError) as exc:
                outcome = AttemptOutcome.ARTIFACT_VALIDATION_ERROR
                error = _make_error("recovered_artifact_validation_error", exc)
        else:
            outcome = AttemptOutcome.INTERRUPTED
            error = _make_error(
                "recovered_interrupted_attempt",
                RuntimeError("Spool attempt has no durable worker response."),
                with_traceback=False,
            )
        worker_pid = authenticated.response.worker_pid if authenticated is not None else None
        _publish_attempt(
            experiment_dir,
            paths,
            request,
            request_sha256,
            outcome=outcome,
            elapsed_ms=0.0,
            process_group_id=worker_pid,
            process_returncode=None,
            hard_timed_out=False,
            spawned_worker_pid=worker_pid,
            authenticated=authenticated,
            error=error,
        )


def _validate_persisted_receipt(
    experiment_dir: Path,
    receipt: AttemptReceipt,
) -> None:
    request_path = _resolve_canonical_path(experiment_dir, receipt.request_path)
    if not request_path.is_file() or sha256_file(request_path) != receipt.request_sha256:
        raise CoordinatorError("Attempt receipt request hash is invalid.")
    request = read_json_model(request_path, MatchWorkerRequest)
    if request.entry != receipt.entry:
        raise CoordinatorError("Attempt receipt entry differs from its canonical request.")
    if request.attempt_number != receipt.attempt_number:
        raise CoordinatorError("Attempt receipt number differs from its canonical request.")
    if request.dispatch_id != receipt.dispatch_id:
        raise CoordinatorError("Attempt receipt dispatch differs from its canonical request.")

    stdout_path = _resolve_canonical_path(experiment_dir, receipt.stdout_path)
    stderr_path = _resolve_canonical_path(experiment_dir, receipt.stderr_path)
    if (
        not stdout_path.is_file()
        or stdout_path.stat().st_size != receipt.stdout_size_bytes
        or sha256_file(stdout_path) != receipt.stdout_sha256
    ):
        raise CoordinatorError("Attempt receipt stdout hash or size is invalid.")
    if (
        not stderr_path.is_file()
        or stderr_path.stat().st_size != receipt.stderr_size_bytes
        or sha256_file(stderr_path) != receipt.stderr_sha256
    ):
        raise CoordinatorError("Attempt receipt stderr hash or size is invalid.")
    if receipt.response_path is not None:
        response_path = _resolve_canonical_path(experiment_dir, receipt.response_path)
        if receipt.response_sha256 is None or sha256_file(response_path) != receipt.response_sha256:
            raise CoordinatorError("Attempt receipt response hash is invalid.")
    elif receipt.response_sha256 is not None:
        raise CoordinatorError("Attempt receipt has a response hash without a response path.")
    if receipt.artifact_path is not None:
        artifact_path = _resolve_canonical_path(experiment_dir, receipt.artifact_path)
        if (
            receipt.artifact_file_sha256 is None
            or receipt.artifact_file_size_bytes is None
            or not artifact_path.is_file()
            or artifact_path.stat().st_size != receipt.artifact_file_size_bytes
            or sha256_file(artifact_path) != receipt.artifact_file_sha256
        ):
            raise CoordinatorError("Attempt receipt artifact hash or size is invalid.")
    elif (
        receipt.artifact_file_sha256 is not None
        or receipt.artifact_file_size_bytes is not None
    ):
        raise CoordinatorError("Attempt receipt hashes an artifact without an artifact path.")
    if receipt.artifact is not None:
        if receipt.artifact_path is None:
            raise CoordinatorError("Validated artifact descriptor has no canonical path.")
        if receipt.artifact.sha256 != receipt.artifact_file_sha256:
            raise CoordinatorError("Validated artifact hash differs from its promoted file hash.")
        artifact_path = _resolve_canonical_path(experiment_dir, receipt.artifact_path)
        read_gzip_json(artifact_path, expected=receipt.artifact)
    if receipt.outcome == AttemptOutcome.COMPLETED and receipt.artifact is None:
        raise CoordinatorError("Completed attempt receipt has no validated artifact.")


def _load_receipts(
    schedule: ConnectedRatingSchedule,
    experiment_dir: Path,
) -> dict[int, list[tuple[AttemptReceipt, str]]]:
    entries_by_index = {entry.schedule_index: entry for entry in schedule.entries}
    grouped: dict[int, list[tuple[AttemptReceipt, str]]] = {}
    seen_attempts: set[tuple[int, int]] = set()
    attempts_root = experiment_dir / "attempts"
    if not attempts_root.exists():
        return grouped
    for receipt_path in sorted(attempts_root.glob("*/attempt-*/receipt.json")):
        receipt = read_json_model(receipt_path, AttemptReceipt)
        entry = entries_by_index.get(receipt.entry.schedule_index)
        if entry is None or receipt.entry != entry:
            raise CoordinatorError(f"Receipt references the wrong schedule entry: {receipt_path}")
        expected_dispatch = _dispatch_id(
            schedule.schedule_hash,
            entry.schedule_index,
            receipt.attempt_number,
        )
        if receipt.dispatch_id != expected_dispatch:
            raise CoordinatorError(f"Receipt has a non-deterministic dispatch id: {receipt_path}")
        identity = (entry.schedule_index, receipt.attempt_number)
        if identity in seen_attempts:
            raise CoordinatorError(f"Duplicate receipt for schedule attempt {identity}")
        seen_attempts.add(identity)
        _validate_persisted_receipt(experiment_dir, receipt)
        grouped.setdefault(entry.schedule_index, []).append(
            (receipt, _relative_path(experiment_dir, receipt_path))
        )
    for receipts in grouped.values():
        receipts.sort(key=lambda item: item[0].attempt_number)
    return grouped


def _record_from_receipt(
    experiment_dir: Path,
    receipt: AttemptReceipt,
    receipt_relative_path: str,
) -> CanonicalMatchRecord:
    receipt_path = _resolve_canonical_path(experiment_dir, receipt_relative_path)
    return CanonicalMatchRecord(
        entry=receipt.entry,
        outcome=receipt.outcome,
        attempt_number=receipt.attempt_number,
        dispatch_id=receipt.dispatch_id,
        receipt_path=receipt_relative_path,
        receipt_sha256=sha256_file(receipt_path),
        worker_status=receipt.worker_status,
        worker_pid=receipt.worker_pid,
        artifact_path=receipt.artifact_path,
        artifact_sha256=receipt.artifact.sha256 if receipt.artifact is not None else None,
        artifact_payload_sha256=(
            receipt.artifact.payload_sha256 if receipt.artifact is not None else None
        ),
        normalized_result_hash=receipt.normalized_result_hash,
        subjectivity_status=receipt.subjectivity_status,
        subjectivity_violation_count=receipt.subjectivity_violation_count,
    )


def _match_record_path(experiment_dir: Path, entry: ConnectedScheduleEntry) -> Path:
    return experiment_dir / "matches" / f"{_attempt_stem(entry)}.json"


def _load_canonical_records(
    schedule: ConnectedRatingSchedule,
    experiment_dir: Path,
    receipts: dict[int, list[tuple[AttemptReceipt, str]]],
) -> list[CanonicalMatchRecord]:
    records: list[CanonicalMatchRecord] = []
    matches_root = experiment_dir / "matches"
    if not matches_root.exists():
        return records
    for path in sorted(matches_root.glob("*.json")):
        record = read_json_model(path, CanonicalMatchRecord)
        index = record.entry.schedule_index
        if index >= len(schedule.entries) or record.entry != schedule.entries[index]:
            raise CoordinatorError(f"Canonical record references the wrong schedule row: {path}")
        if path != _match_record_path(experiment_dir, record.entry):
            raise CoordinatorError(f"Canonical record is stored at a non-canonical path: {path}")
        candidates = receipts.get(index, [])
        matching = [
            (receipt, receipt_path)
            for receipt, receipt_path in candidates
            if receipt.attempt_number == record.attempt_number
            and receipt.dispatch_id == record.dispatch_id
        ]
        if len(matching) != 1:
            raise CoordinatorError(f"Canonical record has no unique attempt receipt: {path}")
        expected = _record_from_receipt(experiment_dir, *matching[0])
        if record != expected:
            raise CoordinatorError(f"Canonical record differs from its attempt receipt: {path}")
        records.append(record)
    observed = [record.entry.schedule_index for record in records]
    if observed != list(range(len(records))):
        raise CoordinatorError("Canonical match records must form a contiguous schedule prefix.")
    return records


def _write_checkpoint(
    experiment_dir: Path,
    schedule: ConnectedRatingSchedule,
    committed_count: int,
) -> None:
    checkpoint = CoordinatorCheckpoint(
        experiment_id=schedule.experiment_id,
        schedule_hash=schedule.schedule_hash,
        scheduled_count=len(schedule.entries),
        completed_schedule_indices=tuple(range(committed_count)),
        next_commit_index=committed_count,
    )
    atomic_write_json(
        experiment_dir / "checkpoint.json",
        checkpoint,
        immutable=False,
    )


def _commit_ready_records(
    experiment_dir: Path,
    schedule: ConnectedRatingSchedule,
    records: list[CanonicalMatchRecord],
    staged: dict[int, tuple[AttemptReceipt, str]],
    committed_during_run: list[int],
) -> None:
    next_index = len(records)
    while next_index in staged:
        receipt, receipt_path = staged.pop(next_index)
        record = _record_from_receipt(experiment_dir, receipt, receipt_path)
        atomic_write_json(
            _match_record_path(experiment_dir, record.entry),
            record,
            immutable=True,
        )
        records.append(record)
        committed_during_run.append(next_index)
        next_index += 1
        _write_checkpoint(experiment_dir, schedule, next_index)


async def _run_locked_coordinator(
    schedule: ConnectedRatingSchedule,
    experiment_dir: Path,
    spool_experiment_dir: Path,
    request_factory: RequestFactory,
    *,
    worker_count: int,
    hard_timeout_seconds: float,
    terminate_grace_seconds: float,
    max_infrastructure_attempts: int,
    resume: bool,
    worker_python: str,
    worker_module: str,
    worker_cwd: Path,
    max_artifact_payload_bytes: int,
) -> CoordinatorSummary:
    durable_paths = (
        experiment_dir / "schedule.json",
        experiment_dir / "attempts",
        experiment_dir / "matches",
        experiment_dir / "checkpoint.json",
        experiment_dir / "summary.json",
    )
    if not resume and any(path.exists() for path in durable_paths):
        raise CoordinatorError("Experiment already has durable state and resume is disabled.")
    atomic_write_json(experiment_dir / "schedule.json", schedule, immutable=True)

    if resume:
        await asyncio.to_thread(
            _recover_spool_attempts,
            schedule,
            experiment_dir,
            spool_experiment_dir,
            max_artifact_payload_bytes=max_artifact_payload_bytes,
        )
    receipts = await asyncio.to_thread(_load_receipts, schedule, experiment_dir)
    records = await asyncio.to_thread(
        _load_canonical_records,
        schedule,
        experiment_dir,
        receipts,
    )
    resumed_record_count = len(records)
    committed_during_run: list[int] = []
    staged: dict[int, tuple[AttemptReceipt, str]] = {}
    pending: deque[_PendingAttempt] = deque()

    for entry in schedule.entries[len(records):]:
        prior_attempts = receipts.get(entry.schedule_index, [])
        if not prior_attempts:
            pending.append(_PendingAttempt(entry, 1))
            continue
        receipt, receipt_path = prior_attempts[-1]
        if receipt.retryable and receipt.attempt_number < max_infrastructure_attempts:
            pending.append(_PendingAttempt(entry, receipt.attempt_number + 1))
        else:
            staged[entry.schedule_index] = (receipt, receipt_path)

    await asyncio.to_thread(
        _commit_ready_records,
        experiment_dir,
        schedule,
        records,
        staged,
        committed_during_run,
    )
    semaphore = asyncio.Semaphore(worker_count)
    active: dict[asyncio.Task[_AttemptExecution], _PendingAttempt] = {}
    spawned_worker_count = 0
    max_active_workers = 0

    async def bounded_execute(item: _PendingAttempt) -> _AttemptExecution:
        async with semaphore:
            return await _execute_attempt(
                schedule,
                experiment_dir,
                spool_experiment_dir,
                item,
                request_factory,
                worker_python=worker_python,
                worker_module=worker_module,
                worker_cwd=worker_cwd,
                hard_timeout_seconds=hard_timeout_seconds,
                terminate_grace_seconds=terminate_grace_seconds,
                max_artifact_payload_bytes=max_artifact_payload_bytes,
            )

    try:
        while pending or active:
            while pending and len(active) < worker_count:
                item = pending.popleft()
                task = asyncio.create_task(bounded_execute(item))
                active[task] = item
            max_active_workers = max(max_active_workers, len(active))
            if not active:
                break
            done, _ = await asyncio.wait(active, return_when=asyncio.FIRST_COMPLETED)
            for task in done:
                item = active.pop(task)
                execution = task.result()
                spawned_worker_count += int(execution.spawned_worker)
                receipt = execution.receipt
                if (
                    receipt.retryable
                    and receipt.attempt_number < max_infrastructure_attempts
                ):
                    pending.append(
                        _PendingAttempt(item.entry, receipt.attempt_number + 1)
                    )
                else:
                    staged[item.entry.schedule_index] = (
                        receipt,
                        execution.receipt_relative_path,
                    )
            await asyncio.to_thread(
                _commit_ready_records,
                experiment_dir,
                schedule,
                records,
                staged,
                committed_during_run,
            )
    finally:
        for task in active:
            task.cancel()
        if active:
            await asyncio.gather(*active, return_exceptions=True)

    if len(records) != len(schedule.entries):
        raise CoordinatorError(
            f"Coordinator stopped with {len(records)} of {len(schedule.entries)} rows committed."
        )
    summary = CoordinatorSummary(
        experiment_id=schedule.experiment_id,
        schedule_hash=schedule.schedule_hash,
        records=tuple(records),
        committed_order=tuple(committed_during_run),
        spawned_worker_count=spawned_worker_count,
        resumed_record_count=resumed_record_count,
        max_active_workers=max_active_workers,
    )
    atomic_write_json(experiment_dir / "summary.json", summary, immutable=False)
    return summary


async def run_isolated_coordinator(
    schedule: ConnectedRatingSchedule,
    *,
    output_root: Path,
    spool_root: Path,
    request_factory: RequestFactory,
    worker_count: int = 4,
    hard_timeout_seconds: float = 135.0,
    terminate_grace_seconds: float = 2.0,
    max_infrastructure_attempts: int = 2,
    resume: bool = True,
    worker_python: str | None = None,
    worker_module: str = _WORKER_MODULE,
    max_artifact_payload_bytes: int = 512 * 1024 * 1024,
) -> CoordinatorSummary:
    """Run or resume a schedule with one fresh process group per attempt."""
    _validate_schedule(schedule)
    if worker_count < 1:
        raise ValueError("worker_count must be at least one.")
    if hard_timeout_seconds <= 0.0:
        raise ValueError("hard_timeout_seconds must be positive.")
    if terminate_grace_seconds <= 0.0:
        raise ValueError("terminate_grace_seconds must be positive.")
    if max_infrastructure_attempts < 1:
        raise ValueError("max_infrastructure_attempts must be at least one.")
    if max_artifact_payload_bytes < 1:
        raise ValueError("max_artifact_payload_bytes must be positive.")

    output_root = Path(output_root).resolve()
    spool_root = Path(spool_root).resolve()
    experiment_dir = output_root / safe_path_component(schedule.experiment_id)
    spool_key = (
        f"{safe_path_component(schedule.experiment_id)}-"
        f"{sha256_bytes(str(experiment_dir).encode('utf-8'))[:16]}"
    )
    spool_experiment_dir = spool_root / spool_key
    if (
        spool_experiment_dir.is_relative_to(experiment_dir)
        or experiment_dir.is_relative_to(spool_experiment_dir)
    ):
        raise ValueError("Private worker spool must be outside the canonical experiment directory.")
    experiment_dir.mkdir(parents=True, exist_ok=True)
    spool_experiment_dir.mkdir(parents=True, exist_ok=True)
    lock = ExperimentLock(
        experiment_dir / ".coordinator.lock",
        metadata={
            "experiment_id": schedule.experiment_id,
            "schedule_hash": schedule.schedule_hash,
            "acquired_at": _utc_now(),
        },
    )
    worker_cwd = Path(__file__).resolve().parents[3]
    with lock:
        return await _run_locked_coordinator(
            schedule,
            experiment_dir,
            spool_experiment_dir,
            request_factory,
            worker_count=worker_count,
            hard_timeout_seconds=hard_timeout_seconds,
            terminate_grace_seconds=terminate_grace_seconds,
            max_infrastructure_attempts=max_infrastructure_attempts,
            resume=resume,
            worker_python=worker_python or sys.executable,
            worker_module=worker_module,
            worker_cwd=worker_cwd,
            max_artifact_payload_bytes=max_artifact_payload_bytes,
        )


def _cli_request_factory(
    schedule: ConnectedRatingSchedule,
    *,
    mode: WorkerTaskMode,
    probe_operation: ProbeOperation,
    probe_delay_seconds: float,
    soft_timeout_seconds: float,
    real_match_entrypoint: str | None,
) -> RequestFactory:
    def build(
        entry: ConnectedScheduleEntry,
        attempt_number: int,
        dispatch_id: str,
    ) -> MatchWorkerRequest:
        expected_hashes = {
            "hero_configuration": entry.hero_configuration_hash,
            "monster_configuration": entry.monster_configuration_hash,
            "battlefield": entry.battlefield_hash,
            "deployment": entry.deployment_hash,
        }
        probe = None
        if mode == WorkerTaskMode.PROBE:
            probe = ProbeTask(
                operation=probe_operation,
                payload={"match_id": entry.match_id},
                delay_seconds=probe_delay_seconds,
                canary_token=f"{entry.match_id}:{attempt_number}",
            )
        return MatchWorkerRequest(
            experiment_id=schedule.experiment_id,
            schedule_hash=schedule.schedule_hash,
            catalog_hash=schedule.catalog_hash,
            entry=entry,
            attempt_number=attempt_number,
            dispatch_id=dispatch_id,
            mode=mode,
            soft_timeout_seconds=soft_timeout_seconds,
            expected_runtime_hashes=expected_hashes,
            probe=probe,
            real_match_entrypoint=real_match_entrypoint,
        )

    return build


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--schedule", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--spool-root", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--hard-timeout", type=float, default=135.0)
    parser.add_argument("--soft-timeout", type=float, default=120.0)
    parser.add_argument("--max-infrastructure-attempts", type=int, default=2)
    parser.add_argument(
        "--mode",
        choices=[mode.value for mode in WorkerTaskMode],
        default=WorkerTaskMode.PROBE.value,
    )
    parser.add_argument(
        "--probe-operation",
        choices=[operation.value for operation in ProbeOperation],
        default=ProbeOperation.ECHO.value,
    )
    parser.add_argument("--probe-delay", type=float, default=0.0)
    parser.add_argument("--real-match-entrypoint")
    parser.add_argument("--no-resume", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """CLI for probe campaigns and future module:callable real-match adapters."""
    arguments = _build_parser().parse_args(argv)
    schedule = read_json_model(arguments.schedule, ConnectedRatingSchedule)
    mode = WorkerTaskMode(arguments.mode)
    if mode == WorkerTaskMode.REAL_MATCH and not arguments.real_match_entrypoint:
        raise SystemExit("--real-match-entrypoint is required in real_match mode")
    factory = _cli_request_factory(
        schedule,
        mode=mode,
        probe_operation=ProbeOperation(arguments.probe_operation),
        probe_delay_seconds=arguments.probe_delay,
        soft_timeout_seconds=arguments.soft_timeout,
        real_match_entrypoint=arguments.real_match_entrypoint,
    )
    summary = asyncio.run(
        run_isolated_coordinator(
            schedule,
            output_root=arguments.output_root,
            spool_root=arguments.spool_root,
            request_factory=factory,
            worker_count=arguments.workers,
            hard_timeout_seconds=arguments.hard_timeout,
            max_infrastructure_attempts=arguments.max_infrastructure_attempts,
            resume=not arguments.no_resume,
        )
    )
    print(json.dumps(summary.model_dump(mode="json"), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
