"""Disposable one-request worker process for configuration-ladder matches."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from contextlib import contextmanager
import ctypes
from datetime import datetime, timezone
import os
import resource
from pathlib import Path
import signal
import subprocess
import sys
import time
import traceback as traceback_module
from typing import Any, Iterator

from ai.evaluation.config_ladder.artifact_store import (
    atomic_write_json,
    sha256_bytes,
    sha256_json,
    write_gzip_json,
)
from ai.evaluation.config_ladder.worker_contracts import (
    MatchWorkerRequest,
    MatchWorkerResponse,
    ProbeOperation,
    RealMatchRunner,
    WorkerArtifactEnvelope,
    WorkerError,
    WorkerStatus,
    WorkerTaskMode,
    WorkerTaskResult,
    WorkerTiming,
)


_PROCESS_CANARIES: set[str] = set()
_PR_SET_PDEATHSIG = 1


class WorkerSoftTimeout(TimeoutError):
    """Raised by the worker-local interrupting deadline."""


class ParentProcessChanged(RuntimeError):
    """Raised when the coordinator died before parent-death binding completed."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _error(code: str, exc: BaseException, *, include_traceback: bool = True) -> WorkerError:
    formatted = traceback_module.format_exc() if include_traceback else None
    if formatted == "NoneType: None\n":
        formatted = None
    return WorkerError(
        code=code,
        exception_type=type(exc).__name__,
        message=str(exc),
        traceback=formatted,
    )


def _install_parent_death_signal(expected_parent_pid: int) -> None:
    """Ask Linux to terminate this worker when its coordinator disappears."""
    if not sys.platform.startswith("linux"):
        return
    libc = ctypes.CDLL(None, use_errno=True)
    result = libc.prctl(_PR_SET_PDEATHSIG, signal.SIGTERM, 0, 0, 0)
    if result != 0:
        error_number = ctypes.get_errno()
        raise OSError(error_number, os.strerror(error_number))
    if os.getppid() != expected_parent_pid:
        raise ParentProcessChanged(
            f"Expected parent {expected_parent_pid}, observed {os.getppid()} after PR_SET_PDEATHSIG."
        )


@contextmanager
def _soft_deadline(seconds: float) -> Iterator[None]:
    """Interrupt a blocking worker task without affecting coordinator deadlines."""
    if not hasattr(signal, "setitimer"):
        yield
        return

    def handle_timeout(signum: int, frame: Any) -> None:
        del signum, frame
        raise WorkerSoftTimeout(f"Worker soft timeout expired after {seconds:.3f}s.")

    previous_handler = signal.getsignal(signal.SIGALRM)
    previous_timer = signal.getitimer(signal.ITIMER_REAL)
    signal.signal(signal.SIGALRM, handle_timeout)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0.0)
        signal.signal(signal.SIGALRM, previous_handler)
        if previous_timer[0] > 0.0:
            signal.setitimer(signal.ITIMER_REAL, *previous_timer)


def _run_probe(request: MatchWorkerRequest) -> WorkerTaskResult:
    probe = request.probe
    if probe is None:
        raise ValueError("Probe mode reached execution without a probe payload.")

    child: subprocess.Popen[bytes] | None = None
    if probe.operation == ProbeOperation.SPAWN_CHILD_AND_SLEEP:
        child = subprocess.Popen(
            [
                sys.executable,
                "-c",
                f"import time; time.sleep({probe.child_sleep_seconds!r})",
            ],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=False,
        )
        print(f"CHILD_PID={child.pid}", flush=True)

    try:
        if probe.canary_token is not None:
            _PROCESS_CANARIES.add(probe.canary_token)
        if probe.delay_seconds > 0.0:
            time.sleep(probe.delay_seconds)
        elif probe.operation == ProbeOperation.SPAWN_CHILD_AND_SLEEP:
            time.sleep(probe.child_sleep_seconds)
        if probe.operation == ProbeOperation.CRASH:
            os._exit(86)

        return WorkerTaskResult(
            status=WorkerStatus.COMPLETED,
            payload={
                "echo": probe.payload,
                "operation": probe.operation.value,
                "worker_pid": os.getpid(),
                "parent_pid": os.getppid(),
                "python_hash_seed": os.environ.get("PYTHONHASHSEED"),
                "expected_runtime_hashes": request.expected_runtime_hashes,
            },
        )
    finally:
        if child is not None and child.poll() is None:
            child.terminate()
            try:
                child.wait(timeout=2.0)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait(timeout=2.0)


def _validate_real_match_identity(
    request: MatchWorkerRequest,
    result: WorkerTaskResult,
) -> WorkerTaskResult:
    if not request.expected_runtime_hashes:
        return result
    observed = result.payload.get("runtime_hashes")
    if observed == request.expected_runtime_hashes:
        return result
    mismatch = RuntimeError(
        "Real-match runner runtime_hashes do not match expected_runtime_hashes."
    )
    return WorkerTaskResult(
        status=WorkerStatus.IDENTITY_ERROR,
        payload={
            "expected_runtime_hashes": request.expected_runtime_hashes,
            "observed_runtime_hashes": observed,
        },
        error=_error("runtime_identity_mismatch", mismatch, include_traceback=False),
    )


def execute_worker_task(
    request: MatchWorkerRequest,
    *,
    real_match_runner: RealMatchRunner | None = None,
) -> WorkerTaskResult:
    """Execute one typed task; injectable runner is the future engine seam."""
    observed_hash_seed = os.environ.get("PYTHONHASHSEED")
    if observed_hash_seed != request.python_hash_seed:
        mismatch = RuntimeError(
            f"Expected PYTHONHASHSEED={request.python_hash_seed!r}, observed {observed_hash_seed!r}."
        )
        return WorkerTaskResult(
            status=WorkerStatus.IDENTITY_ERROR,
            payload={
                "expected_python_hash_seed": request.python_hash_seed,
                "observed_python_hash_seed": observed_hash_seed,
            },
            error=_error("python_hash_seed_mismatch", mismatch, include_traceback=False),
        )

    if request.mode == WorkerTaskMode.PROBE:
        result = _run_probe(request)
    else:
        runner = real_match_runner
        if runner is None:
            unsupported = RuntimeError(
                "No statically bound real-match runner was provided by this worker entry module."
            )
            return WorkerTaskResult(
                status=WorkerStatus.UNSUPPORTED,
                error=_error("real_match_runner_missing", unsupported, include_traceback=False),
            )
        result = WorkerTaskResult.model_validate(runner(request))
        result = _validate_real_match_identity(request, result)

    if result.normalized_result_hash is None:
        result = result.model_copy(
            update={"normalized_result_hash": sha256_json(result.payload)}
        )
    return result


def run_worker(
    request_path: Path,
    response_path: Path,
    artifact_path: Path,
    *,
    parent_pid: int,
    real_match_runner: RealMatchRunner | None = None,
) -> int:
    """Run one request and publish artifact-before-response into private spool."""
    request_bytes = Path(request_path).read_bytes()
    request_sha256 = sha256_bytes(request_bytes)
    request = MatchWorkerRequest.model_validate_json(request_bytes)
    _install_parent_death_signal(parent_pid)

    started_at = _utc_now()
    total_started = time.monotonic()
    task_started = time.monotonic()
    canaries_before = tuple(sorted(_PROCESS_CANARIES))
    try:
        with _soft_deadline(request.soft_timeout_seconds):
            result = execute_worker_task(request, real_match_runner=real_match_runner)
    except WorkerSoftTimeout as exc:
        result = WorkerTaskResult(
            status=WorkerStatus.SOFT_TIMEOUT,
            error=_error("worker_soft_timeout", exc),
        )
    except BaseException as exc:
        result = WorkerTaskResult(
            status=WorkerStatus.TASK_ERROR,
            error=_error("worker_task_error", exc),
        )
    task_ms = (time.monotonic() - task_started) * 1000.0
    if result.normalized_result_hash is None:
        result = result.model_copy(
            update={"normalized_result_hash": sha256_json(result.payload)}
        )
    canaries_after = tuple(sorted(_PROCESS_CANARIES))

    envelope = WorkerArtifactEnvelope(
        request_sha256=request_sha256,
        request=request,
        worker_pid=os.getpid(),
        parent_pid=os.getppid(),
        observed_python_hash_seed=os.environ.get("PYTHONHASHSEED"),
        process_canaries_before=canaries_before,
        process_canaries_after=canaries_after,
        result=result,
    )
    serialization_started = time.monotonic()
    descriptor = write_gzip_json(Path(artifact_path), envelope)
    serialization_ms = (time.monotonic() - serialization_started) * 1000.0
    total_ms = (time.monotonic() - total_started) * 1000.0
    usage = resource.getrusage(resource.RUSAGE_SELF)

    response = MatchWorkerResponse(
        experiment_id=request.experiment_id,
        schedule_hash=request.schedule_hash,
        match_id=request.entry.match_id,
        schedule_index=request.entry.schedule_index,
        attempt_number=request.attempt_number,
        dispatch_id=request.dispatch_id,
        request_sha256=request_sha256,
        worker_pid=os.getpid(),
        parent_pid=os.getppid(),
        started_at=started_at,
        completed_at=_utc_now(),
        status=result.status,
        artifact=descriptor,
        manifest_hash=result.manifest_hash,
        normalized_result_hash=result.normalized_result_hash,
        subjectivity_status=result.subjectivity_status,
        subjectivity_violation_count=result.subjectivity_violation_count,
        timing=WorkerTiming(
            task_ms=task_ms,
            serialization_ms=serialization_ms,
            total_ms=total_ms,
            user_cpu_seconds=usage.ru_utime,
            system_cpu_seconds=usage.ru_stime,
            peak_rss_mb=usage.ru_maxrss / 1024.0,
        ),
        error=result.error,
    )
    atomic_write_json(Path(response_path), response, immutable=True)
    return {
        WorkerStatus.COMPLETED: 0,
        WorkerStatus.SOFT_TIMEOUT: 20,
        WorkerStatus.TASK_ERROR: 21,
        WorkerStatus.IDENTITY_ERROR: 22,
        WorkerStatus.UNSUPPORTED: 23,
    }[result.status]


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--response", type=Path, required=True)
    parser.add_argument("--artifact", type=Path, required=True)
    parser.add_argument("--parent-pid", type=int, required=True)
    return parser


def main(
    argv: Sequence[str] | None = None,
    *,
    real_match_runner: RealMatchRunner | None = None,
) -> int:
    """CLI entry point used directly by the coordinator's Python interpreter."""
    arguments = _build_parser().parse_args(argv)
    try:
        return run_worker(
            arguments.request,
            arguments.response,
            arguments.artifact,
            parent_pid=arguments.parent_pid,
            real_match_runner=real_match_runner,
        )
    except BaseException:
        traceback_module.print_exc(file=sys.stderr)
        return 70


if __name__ == "__main__":
    raise SystemExit(main())
