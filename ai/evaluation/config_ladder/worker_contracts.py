"""Strict contracts for isolated configuration-ladder worker processes."""

from __future__ import annotations

from enum import Enum
from typing import Annotated, Any, Callable, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ai.evaluation.config_ladder.contracts import ConnectedScheduleEntry
from ai.evaluation.promotion.contracts import PromotionScheduleEntry


ScheduleEntry = ConnectedScheduleEntry | PromotionScheduleEntry


Sha256Hex = Annotated[
    str,
    Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$"),
]
DEFAULT_RATING_MAX_COMMANDS = 400


class StrictFrozenModel(BaseModel):
    """Immutable protocol model that rejects unknown fields."""

    model_config = ConfigDict(frozen=True, extra="forbid")


class WorkerTaskMode(str, Enum):
    """Kind of work executed by one fresh interpreter."""

    PROBE = "probe"
    REAL_MATCH = "real_match"


class ProbeOperation(str, Enum):
    """Deterministic operations used to prove worker isolation."""

    ECHO = "echo"
    SLEEP = "sleep"
    CRASH = "crash"
    SPAWN_CHILD_AND_SLEEP = "spawn_child_and_sleep"


class WorkerStatus(str, Enum):
    """Status written by a worker that reached the response boundary."""

    COMPLETED = "completed"
    SOFT_TIMEOUT = "soft_timeout"
    TASK_ERROR = "task_error"
    IDENTITY_ERROR = "identity_error"
    UNSUPPORTED = "unsupported"


class AttemptOutcome(str, Enum):
    """Coordinator-authenticated terminal result of one attempt."""

    COMPLETED = "completed"
    SOFT_TIMEOUT = "soft_timeout"
    TASK_ERROR = "task_error"
    IDENTITY_ERROR = "identity_error"
    UNSUPPORTED = "unsupported"
    HARD_TIMEOUT = "hard_timeout"
    WORKER_CRASH = "worker_crash"
    PROTOCOL_ERROR = "protocol_error"
    ARTIFACT_VALIDATION_ERROR = "artifact_validation_error"
    PROCESS_LEAK = "process_leak"
    SPAWN_ERROR = "spawn_error"
    INTERRUPTED = "interrupted"


class ProbeTask(StrictFrozenModel):
    """Typed process-isolation probe executed instead of a real match."""

    operation: ProbeOperation = Field(description="Probe operation to execute.")
    payload: dict[str, Any] = Field(default_factory=dict, description="JSON payload echoed into probe evidence.")
    delay_seconds: float = Field(default=0.0, ge=0.0, description="Delay before completing or crashing.")
    child_sleep_seconds: float = Field(
        default=60.0,
        gt=0.0,
        description="Lifetime of the descendant created by the process-group probe.",
    )
    canary_token: str | None = Field(
        default=None,
        description="Marker added to worker-local state after its initial state is captured.",
    )


class MatchWorkerRequest(StrictFrozenModel):
    """Immutable request consumed by exactly one worker interpreter."""

    schema_version: Literal[1] = Field(default=1, description="Worker request schema version.")
    experiment_id: str = Field(min_length=1, description="Owning connected-rating experiment.")
    schedule_hash: str = Field(min_length=1, description="Hash of the immutable connected schedule.")
    catalog_hash: str = Field(min_length=1, description="Hash of the immutable scenario catalog.")
    entry: ScheduleEntry = Field(description="Complete scheduled row executed by this worker.")
    attempt_number: int = Field(ge=1, description="One-based attempt number for this row.")
    dispatch_id: str = Field(min_length=1, description="Unique dispatch identity preventing stale response reuse.")
    mode: WorkerTaskMode = Field(description="Probe or future real-match execution mode.")
    max_commands: int = Field(
        default=DEFAULT_RATING_MAX_COMMANDS,
        ge=1,
        description="Emergency command ceiling above the finite-horizon draw window.",
    )
    soft_timeout_seconds: float = Field(default=120.0, gt=0.0, description="Worker-local interrupting deadline.")
    python_hash_seed: str = Field(default="0", min_length=1, description="Required child PYTHONHASHSEED value.")
    expected_runtime_hashes: dict[str, str] = Field(
        default_factory=dict,
        description="Expected engine, ruleset, policy, controller, and witness identities.",
    )
    catalog_snapshot_path: str | None = Field(
        default=None,
        description="Absolute path to the immutable typed catalog used by a real match.",
    )
    catalog_snapshot_hash: str | None = Field(
        default=None,
        description="Expected mechanical and runtime hash embedded in the catalog snapshot.",
    )
    probe: ProbeTask | None = Field(default=None, description="Probe definition when mode is probe.")
    real_match_entrypoint: str | None = Field(
        default=None,
        description="Optional module:callable entry point returning WorkerTaskResult for real-match mode.",
    )

    @model_validator(mode="after")
    def validate_mode_payload(self) -> MatchWorkerRequest:
        """Require exactly the payload needed by the selected mode."""
        if self.mode == WorkerTaskMode.PROBE and self.probe is None:
            raise ValueError("Probe mode requires a probe payload.")
        if self.mode == WorkerTaskMode.REAL_MATCH and self.probe is not None:
            raise ValueError("Real-match mode cannot contain a probe payload.")
        if self.mode == WorkerTaskMode.REAL_MATCH and self.catalog_snapshot_path is None:
            raise ValueError("Real-match mode requires an immutable catalog snapshot path.")
        if self.mode == WorkerTaskMode.REAL_MATCH and self.catalog_snapshot_hash is None:
            raise ValueError("Real-match mode requires an immutable catalog snapshot hash.")
        return self


class WorkerError(StrictFrozenModel):
    """Typed error retained when a worker reaches its response boundary."""

    code: str = Field(description="Stable machine-readable error code.")
    exception_type: str = Field(description="Raised exception class name.")
    message: str = Field(description="Human-readable failure message.")
    traceback: str | None = Field(default=None, description="Formatted traceback when available.")


class WorkerTaskResult(StrictFrozenModel):
    """Engine-independent value returned by probe and future match runners."""

    status: WorkerStatus = Field(description="Task status before artifact serialization.")
    payload: dict[str, Any] = Field(default_factory=dict, description="Complete typed task result payload.")
    manifest_hash: str | None = Field(default=None, description="Precombat manifest hash for real matches.")
    normalized_result_hash: str | None = Field(
        default=None,
        description="UUID-independent semantic result hash, computed by the worker when omitted.",
    )
    subjectivity_status: str = Field(default="not_run", description="Independent subjectivity witness status.")
    subjectivity_violation_count: int = Field(default=0, ge=0, description="Detected subjectivity violations.")
    error: WorkerError | None = Field(default=None, description="Typed task error when status is not completed.")


class ArtifactDescriptor(StrictFrozenModel):
    """Integrity metadata for one immutable compressed artifact."""

    file_name: str = Field(description="Attempt-local artifact filename.")
    compression: Literal["gzip"] = Field(default="gzip", description="Artifact compression format.")
    sha256: Sha256Hex = Field(description="SHA-256 of exact compressed bytes.")
    size_bytes: int = Field(ge=0, description="Compressed artifact size.")
    payload_sha256: Sha256Hex = Field(description="SHA-256 of canonical JSON payload bytes.")
    payload_size_bytes: int = Field(ge=0, description="Uncompressed canonical JSON size.")


class WorkerTiming(StrictFrozenModel):
    """Worker-local wall-clock stage timings."""

    task_ms: float = Field(ge=0.0, description="Task execution duration.")
    serialization_ms: float = Field(ge=0.0, description="Artifact serialization duration.")
    total_ms: float = Field(ge=0.0, description="Total worker duration through artifact publication.")
    user_cpu_seconds: float = Field(default=0.0, ge=0.0, description="Worker user CPU time through publication.")
    system_cpu_seconds: float = Field(default=0.0, ge=0.0, description="Worker system CPU time through publication.")
    peak_rss_mb: float = Field(default=0.0, ge=0.0, description="Maximum worker resident memory in MiB.")


class WorkerArtifactEnvelope(StrictFrozenModel):
    """Full evidence payload written privately by one worker."""

    schema_version: Literal[1] = Field(default=1, description="Worker artifact schema version.")
    request_sha256: Sha256Hex = Field(description="Hash of exact request file bytes.")
    request: MatchWorkerRequest = Field(description="Request bound to this evidence.")
    worker_pid: int = Field(gt=0, description="Worker process id.")
    parent_pid: int = Field(gt=0, description="Observed coordinator process id.")
    observed_python_hash_seed: str | None = Field(description="PYTHONHASHSEED observed by the worker.")
    process_canaries_before: tuple[str, ...] = Field(description="Worker-local markers present before this task.")
    process_canaries_after: tuple[str, ...] = Field(description="Worker-local markers present after this task.")
    result: WorkerTaskResult = Field(description="Probe or real-match task result.")


class MatchWorkerResponse(StrictFrozenModel):
    """Small ready marker written after the private artifact is durable."""

    schema_version: Literal[1] = Field(default=1, description="Worker response schema version.")
    experiment_id: str = Field(description="Echoed experiment identity.")
    schedule_hash: str = Field(description="Echoed schedule hash.")
    match_id: str = Field(description="Echoed match identity.")
    schedule_index: int = Field(ge=0, description="Echoed canonical schedule index.")
    attempt_number: int = Field(ge=1, description="Echoed attempt number.")
    dispatch_id: str = Field(description="Echoed dispatch identity.")
    request_sha256: Sha256Hex = Field(description="Hash of exact request bytes.")
    worker_pid: int = Field(gt=0, description="Worker process id.")
    parent_pid: int = Field(gt=0, description="Observed coordinator process id.")
    started_at: str = Field(description="UTC worker start timestamp.")
    completed_at: str = Field(description="UTC response timestamp.")
    status: WorkerStatus = Field(description="Worker-reported terminal status.")
    artifact: ArtifactDescriptor | None = Field(default=None, description="Private artifact descriptor when written.")
    manifest_hash: str | None = Field(default=None, description="Precombat manifest hash for real matches.")
    normalized_result_hash: str | None = Field(default=None, description="Semantic result hash.")
    subjectivity_status: str = Field(default="not_run", description="Subjectivity witness status.")
    subjectivity_violation_count: int = Field(default=0, ge=0, description="Subjectivity violation count.")
    timing: WorkerTiming = Field(description="Worker-local timings.")
    error: WorkerError | None = Field(default=None, description="Typed worker error.")


class AttemptReceipt(StrictFrozenModel):
    """Coordinator-authenticated, resumable evidence for one attempt."""

    schema_version: Literal[1] = Field(default=1, description="Attempt receipt schema version.")
    entry: ScheduleEntry = Field(description="Scheduled row attempted.")
    attempt_number: int = Field(ge=1, description="One-based attempt number.")
    dispatch_id: str = Field(description="Unique dispatch identity.")
    outcome: AttemptOutcome = Field(description="Coordinator-authenticated attempt outcome.")
    retryable: bool = Field(description="Whether this failure class permits an infrastructure retry.")
    worker_status: WorkerStatus | None = Field(default=None, description="Validated worker status when available.")
    worker_pid: int | None = Field(default=None, gt=0, description="Observed worker process id.")
    process_group_id: int | None = Field(default=None, gt=0, description="Dedicated worker process group id.")
    process_returncode: int | None = Field(default=None, description="Return code observed by the coordinator.")
    hard_timed_out: bool = Field(default=False, description="Whether the coordinator deadline expired.")
    elapsed_ms: float = Field(ge=0.0, description="Coordinator-observed attempt duration.")
    request_sha256: Sha256Hex = Field(description="Exact request file hash.")
    response_sha256: Sha256Hex | None = Field(default=None, description="Exact response file hash when present.")
    artifact: ArtifactDescriptor | None = Field(default=None, description="Validated canonical artifact descriptor.")
    artifact_file_sha256: Sha256Hex | None = Field(
        default=None,
        description="Exact promoted artifact hash, including untrusted forensic artifacts.",
    )
    artifact_file_size_bytes: int | None = Field(
        default=None,
        ge=0,
        description="Exact promoted artifact size when an artifact file exists.",
    )
    normalized_result_hash: str | None = Field(default=None, description="Validated semantic result hash.")
    subjectivity_status: str = Field(default="not_run", description="Validated subjectivity status.")
    subjectivity_violation_count: int = Field(default=0, ge=0, description="Validated subjectivity violations.")
    request_path: str = Field(description="Experiment-relative canonical request path.")
    response_path: str | None = Field(default=None, description="Experiment-relative canonical response path.")
    artifact_path: str | None = Field(default=None, description="Experiment-relative canonical artifact path.")
    stdout_path: str = Field(description="Experiment-relative worker stdout path.")
    stdout_sha256: Sha256Hex = Field(description="Exact worker stdout hash.")
    stdout_size_bytes: int = Field(ge=0, description="Exact worker stdout size.")
    stderr_path: str = Field(description="Experiment-relative worker stderr path.")
    stderr_sha256: Sha256Hex = Field(description="Exact worker stderr hash.")
    stderr_size_bytes: int = Field(ge=0, description="Exact worker stderr size.")
    error: WorkerError | None = Field(default=None, description="Coordinator or worker failure details.")


class CanonicalMatchRecord(StrictFrozenModel):
    """Schedule-ordered canonical row written only by the coordinator."""

    schema_version: Literal[1] = Field(default=1, description="Canonical record schema version.")
    entry: ScheduleEntry = Field(description="Exact immutable schedule row.")
    outcome: AttemptOutcome = Field(description="Accepted terminal attempt outcome.")
    attempt_number: int = Field(ge=1, description="Attempt selected for this row.")
    dispatch_id: str = Field(description="Selected attempt dispatch identity.")
    receipt_path: str = Field(description="Experiment-relative immutable attempt receipt path.")
    receipt_sha256: Sha256Hex = Field(description="Exact selected attempt receipt hash.")
    worker_status: WorkerStatus | None = Field(default=None, description="Worker-reported status when available.")
    worker_pid: int | None = Field(default=None, description="Worker process id retained for isolation evidence.")
    artifact_path: str | None = Field(default=None, description="Experiment-relative compressed artifact path.")
    artifact_sha256: Sha256Hex | None = Field(default=None, description="Compressed artifact SHA-256.")
    artifact_payload_sha256: Sha256Hex | None = Field(default=None, description="Uncompressed artifact payload SHA-256.")
    normalized_result_hash: str | None = Field(default=None, description="UUID-independent semantic result hash.")
    subjectivity_status: str = Field(default="not_run", description="Subjectivity witness status.")
    subjectivity_violation_count: int = Field(default=0, ge=0, description="Subjectivity violation count.")


class CoordinatorCheckpoint(StrictFrozenModel):
    """Compact progress projection derived from canonical match records."""

    schema_version: Literal[1] = Field(default=1, description="Checkpoint schema version.")
    experiment_id: str = Field(description="Experiment identity.")
    schedule_hash: str = Field(description="Immutable schedule hash.")
    scheduled_count: int = Field(ge=0, description="Total scheduled rows.")
    completed_schedule_indices: tuple[int, ...] = Field(description="Canonical contiguous committed prefix.")
    next_commit_index: int = Field(ge=0, description="Next schedule index eligible for commit.")


class CoordinatorSummary(StrictFrozenModel):
    """Result returned after a coordinator run or resume."""

    schema_version: Literal[1] = Field(default=1, description="Coordinator summary schema version.")
    experiment_id: str = Field(description="Experiment identity.")
    schedule_hash: str = Field(description="Immutable schedule hash.")
    records: tuple[CanonicalMatchRecord, ...] = Field(description="Canonical schedule-ordered records.")
    committed_order: tuple[int, ...] = Field(description="Indices committed during this invocation.")
    spawned_worker_count: int = Field(ge=0, description="Fresh worker interpreters spawned this invocation.")
    resumed_record_count: int = Field(ge=0, description="Canonical records reused at startup.")
    max_active_workers: int = Field(ge=0, description="Maximum simultaneous worker processes.")


class RealMatchRunner(Protocol):
    """Future engine-bound callable seam used by one worker process."""

    def __call__(self, request: MatchWorkerRequest) -> WorkerTaskResult:
        """Execute one real match and return engine-independent evidence."""
        ...


RequestFactory = Callable[[ScheduleEntry, int, str], MatchWorkerRequest]
