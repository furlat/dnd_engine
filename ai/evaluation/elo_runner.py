"""CLI and runner for complete Elo matrix gauntlet evaluation."""

from __future__ import annotations

from collections import Counter, deque
from contextlib import contextmanager
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import signal
import threading
import time
import traceback as traceback_module
from typing import Any, Iterator, Optional

import httpx
import typer

from ai.evaluation.arena_manifest import build_arena_manifest
from ai.evaluation.artifacts import (
    ValidationRunArtifact,
    build_external_selfplay_artifact,
    write_validation_run_artifact,
)
from ai.evaluation.elo_contract import (
    ArenaManifest,
    EloCoverageSummary,
    EloEligibility,
    EloGauntletCheckpoint,
    EloGauntletEvent,
    EloGauntletEventSink,
    EloGauntletEventType,
    EloGauntletSummary,
    EloMatrixMode,
    EloMatrixSchedule,
    EloMatrixScheduleEntry,
    EloMatchFailureArtifact,
    EloMatchRecord,
)
from ai.evaluation.gauntlet_contract import GauntletEvent, GauntletEventType
from ai.evaluation.elo_dashboard_projection import project_elo_dashboard
from ai.evaluation.elo_matrix import DEFAULT_SIDE_ORDERS, build_elo_matrix_schedule
from ai.evaluation.elo_performance import analyze_elo_performance
from ai.evaluation.elo_ratings import EloLedgerBook, audit_evaluator_rating_eligibility, build_match_participants
from ai.evaluation.tournament import EloConfig, TournamentMatchRecord, build_tournament_match_record
from ai.evaluation.elo_validation import validate_elo_summary
from ai.external_selfplay import run_external_selfplay
from ai.policy.source import CONTROLLER_PROFILE, POLICY_VERSION, policy_source_snapshot
from dnd.scenarios.ai_validation_arenas import ValidationArena


app = typer.Typer(help="Complete Elo matrix gauntlet evaluator.")


class EloMatchTimeoutError(TimeoutError):
    """Raised when one synchronous self-play row exceeds its deadline."""


@contextmanager
def _match_deadline(timeout_seconds: float) -> Iterator[None]:
    """Interrupt one synchronous match when its wall-clock deadline expires.

    The engine uses process-global registries, so running a match in a worker
    thread or process would change its isolation and evidence semantics. On the
    supported WSL/POSIX evaluator runtime, ``SIGALRM`` interrupts the same
    synchronous execution without duplicating engine state.

    Args:
        timeout_seconds: Positive wall-clock deadline in seconds.

    Raises:
        ValueError: If the deadline is not positive.
        RuntimeError: If the process cannot provide an interrupting deadline.
        EloMatchTimeoutError: If the deadline expires.
    """
    if timeout_seconds <= 0:
        raise ValueError("match_timeout_seconds must be positive")
    if threading.current_thread() is not threading.main_thread() or not hasattr(signal, "SIGALRM"):
        raise RuntimeError("Interrupting Elo match deadlines require the POSIX main thread")
    prior_delay, prior_interval = signal.getitimer(signal.ITIMER_REAL)
    if prior_delay > 0 or prior_interval > 0:
        raise RuntimeError("Cannot install an Elo match deadline while another real-time timer is active")
    prior_handler = signal.getsignal(signal.SIGALRM)

    def raise_timeout(_signum: int, _frame: object) -> None:
        raise EloMatchTimeoutError(
            f"Self-play exceeded the {timeout_seconds:.3f}s wall-clock deadline"
        )

    signal.signal(signal.SIGALRM, raise_timeout)
    signal.setitimer(signal.ITIMER_REAL, timeout_seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, prior_handler)


class EloGauntletEventStream:
    """Small bounded event stream for live Elo evaluator watchers."""

    def __init__(self, *, max_events: int = 2048) -> None:
        """Create an empty stream.

        Args:
            max_events: Maximum retained event count.
        """
        self._events: deque[EloGauntletEvent] = deque(maxlen=max_events)
        self._cursor = 0

    def append(
        self,
        *,
        event_type: EloGauntletEventType,
        matrix_id: str,
        match_id: Optional[str] = None,
        match_index: Optional[int] = None,
        status: Optional[str] = None,
        message: Optional[str] = None,
        payload: Optional[dict[str, Any]] = None,
    ) -> EloGauntletEvent:
        """Append one watcher event."""
        self._cursor += 1
        event = EloGauntletEvent(
            cursor=self._cursor,
            event_type=event_type,
            matrix_id=matrix_id,
            match_id=match_id,
            match_index=match_index,
            status=status,
            message=message,
            payload=payload or {},
            created_at=_utc_now(),
        )
        self._events.append(event)
        return event

    def since(self, cursor: int = 0) -> list[EloGauntletEvent]:
        """Return retained events after `cursor`."""
        return [event for event in self._events if event.cursor > cursor]


class HttpMirroringEloGauntletEventStream:
    """Retain Elo events locally and mirror them into the shared live watcher."""

    def __init__(self, base_url: str, client: Optional[httpx.Client] = None) -> None:
        """Create a mirror for the server's shared gauntlet event endpoint."""
        self.base_url = base_url.rstrip("/")
        self._local = EloGauntletEventStream()
        self._client = client or httpx.Client(base_url=self.base_url, timeout=10.0)
        self._owns_client = client is None

    def append(
        self,
        *,
        event_type: EloGauntletEventType,
        matrix_id: str,
        match_id: Optional[str] = None,
        match_index: Optional[int] = None,
        status: Optional[str] = None,
        message: Optional[str] = None,
        payload: Optional[dict[str, Any]] = None,
    ) -> EloGauntletEvent:
        """Append locally and publish a watcher-compatible event envelope."""
        event = self._local.append(
            event_type=event_type,
            matrix_id=matrix_id,
            match_id=match_id,
            match_index=match_index,
            status=status,
            message=message,
            payload=payload,
        )
        watcher_payload: dict[str, object] = {
            **event.payload,
            "event_family": "elo",
            "elo_event_type": event.event_type,
            "matrix_id": event.matrix_id,
        }
        watcher_event = GauntletEvent(
            cursor=event.cursor,
            event_type=_watcher_event_type(event.event_type),
            gauntlet_id=event.matrix_id,
            match_id=event.match_id,
            match_index=event.match_index,
            status=event.status,
            message=event.message,
            payload=watcher_payload,
            created_at=event.created_at,
        )
        response = self._client.post(
            "/ai/gauntlets/events",
            json={"events": [watcher_event.model_dump(mode="json")]},
        )
        response.raise_for_status()
        return event

    def since(self, cursor: int = 0) -> list[EloGauntletEvent]:
        """Return local retained Elo events after a cursor."""
        return self._local.since(cursor)

    def close(self) -> None:
        """Close the HTTP client when this stream created it."""
        if self._owns_client:
            self._client.close()


def run_elo_gauntlet(
    schedule: EloMatrixSchedule,
    *,
    max_commands: int = 240,
    elo_config: Optional[EloConfig] = None,
    runs_output_directory: Optional[Path | str] = None,
    summary_output_directory: Path | str = "ai/evidence/elo_gauntlets",
    resume: bool = True,
    retry_ineligible: bool = False,
    match_timeout_seconds: float = 120.0,
    require_complete: bool = False,
    require_rating_eligible: bool = False,
    event_stream: Optional[EloGauntletEventSink] = None,
) -> EloGauntletSummary:
    """Run or resume a complete Elo matrix gauntlet.

    Args:
        schedule: Deterministic matrix schedule.
        max_commands: Command cap per match.
        elo_config: Rating configuration.
        runs_output_directory: Optional raw artifact directory.
        summary_output_directory: Root directory for matrix summaries.
        resume: Whether to reuse matching retained records.
        retry_ineligible: Whether to archive and rerun retained ineligible rows.
        match_timeout_seconds: Interrupting wall-clock deadline for each match.
        require_complete: Raise when final summary remains partial.
        require_rating_eligible: Raise when any row is skipped from ratings.
        event_stream: Optional watcher event sink.

    Returns:
        Retained summary.
    """
    stream = event_stream or EloGauntletEventStream()
    config = elo_config or EloConfig()
    root = Path(summary_output_directory)
    matrix_dir = root / schedule.matrix_id
    matches_dir = matrix_dir / "matches"
    artifact_dir = Path(runs_output_directory) if runs_output_directory is not None else matrix_dir / "runs"
    checkpoint_dir = matrix_dir / "checkpoints"
    if not resume and matrix_dir.exists() and any(matrix_dir.iterdir()):
        raise ValueError(
            "Cannot run an existing Elo matrix with resume disabled. "
            "Build a new schedule so retained evidence is never overwritten or relabeled."
        )
    for directory in (matrix_dir, matches_dir, artifact_dir, checkpoint_dir):
        directory.mkdir(parents=True, exist_ok=True)

    previous_records = _load_resume_records(schedule, matrix_dir) if resume else []
    retry_metadata: dict[int, tuple[int, list[str]]] = {}
    retained_records: list[EloMatchRecord] = []
    if retry_ineligible:
        _validate_retry_policy_identity(schedule)
    for record in previous_records:
        if retry_ineligible and not record.eligibility.rating_eligible:
            archived_path = _archive_match_attempt(matrix_dir, record)
            retry_metadata[record.match_index] = (
                record.attempt_number + 1,
                [*record.prior_attempt_record_paths, str(archived_path)],
            )
            continue
        retained_records.append(record)
    _write_json(matrix_dir / "schedule.json", schedule.model_dump(mode="json"))
    records_by_index = {record.match_index: record for record in retained_records}
    ledger_book = EloLedgerBook(elo_config=config)
    for record in sorted(retained_records, key=lambda row: row.match_index):
        _replay_record_into_ledgers(ledger_book, record)

    stream.append(
        event_type="ELO_GAUNTLET_STARTED",
        matrix_id=schedule.matrix_id,
        status="running",
        payload={
            "mode": schedule.mode,
            "scheduled_count": len(schedule.entries),
            "resume_count": len(retained_records),
            "retry_count": len(retry_metadata),
        },
    )

    for match_index, (attempt_number, prior_paths) in sorted(retry_metadata.items()):
        entry = schedule.entries[match_index]
        stream.append(
            event_type="ELO_MATCH_RETRY_SCHEDULED",
            matrix_id=schedule.matrix_id,
            match_id=_match_id(schedule, entry),
            match_index=match_index,
            status="retry_scheduled",
            payload={"attempt_number": attempt_number, "prior_attempt_record_paths": prior_paths},
        )

    for entry in schedule.entries:
        if entry.match_index in records_by_index:
            continue
        match_id = _match_id(schedule, entry)
        stream.append(
            event_type="ELO_MATCH_STARTED",
            matrix_id=schedule.matrix_id,
            match_id=match_id,
            match_index=entry.match_index,
            status="running",
            payload={"arena_id": entry.arena_id, "seed": entry.random_seed, "side_order": entry.side_order_id},
        )
        attempt_number, prior_attempt_paths = retry_metadata.get(entry.match_index, (1, []))
        record = _run_one_entry(
            schedule=schedule,
            entry=entry,
            match_id=match_id,
            attempt_number=attempt_number,
            max_commands=max_commands,
            match_timeout_seconds=match_timeout_seconds,
            artifact_dir=artifact_dir,
            ledger_book=ledger_book,
            elo_config=config,
            stream=stream,
        )
        if prior_attempt_paths:
            record = record.model_copy(update={
                "attempt_number": attempt_number,
                "prior_attempt_record_paths": prior_attempt_paths,
            })
        records_by_index[entry.match_index] = record
        _write_json(matches_dir / f"{match_id}.json", record.model_dump(mode="json"))
        checkpoint = _build_checkpoint(
            schedule=schedule,
            records=sorted(records_by_index.values(), key=lambda row: row.match_index),
            generated_at=_utc_now(),
        )
        _write_json(checkpoint_dir / "latest.partial.json", checkpoint.model_dump(mode="json"))
        stream.append(
            event_type="ELO_CHECKPOINT_WRITTEN",
            matrix_id=schedule.matrix_id,
            match_id=match_id,
            match_index=entry.match_index,
            status="checkpoint",
            payload={"completed_count": checkpoint.completed_count, "pending_count": checkpoint.pending_count},
        )

    ordered_records = sorted(records_by_index.values(), key=lambda row: row.match_index)
    ledger_book = _rebuild_ledgers(ordered_records, config)
    _write_match_records(matches_dir, ordered_records)
    final_summary = _build_summary(
        schedule=schedule,
        records=ordered_records,
        ledger_book=ledger_book,
        events=stream.since(0),
        generated_at=_utc_now(),
    )
    event_type: EloGauntletEventType = "ELO_GAUNTLET_COMPLETED" if final_summary.gate_status == "passed" else "ELO_GAUNTLET_FAILED"
    stream.append(event_type=event_type, matrix_id=schedule.matrix_id, status=final_summary.gate_status, payload={"gate_reasons": final_summary.gate_reasons})
    final_summary = final_summary.model_copy(update={"events": stream.since(0)})
    _write_final_summary(final_summary, root, matrix_dir)
    if require_complete and final_summary.completion_status != "completed":
        raise typer.Exit(1)
    if require_rating_eligible and final_summary.skipped_rating_count:
        raise typer.Exit(1)
    return final_summary


def _run_one_entry(
    *,
    schedule: EloMatrixSchedule,
    entry: EloMatrixScheduleEntry,
    match_id: str,
    attempt_number: int,
    max_commands: int,
    match_timeout_seconds: float,
    artifact_dir: Path,
    ledger_book: EloLedgerBook,
    elo_config: EloConfig,
    stream: EloGauntletEventSink,
) -> EloMatchRecord:
    entry_started = time.perf_counter()
    manifest: Optional[ArenaManifest] = None
    artifact_paths: list[str] = []
    policy_identity = policy_source_snapshot()
    runtime_policy_version: Optional[str] = policy_identity.policy_version
    runtime_policy_source_hash: Optional[str] = policy_identity.source_sha256
    runtime_controller_profile: Optional[str] = CONTROLLER_PROFILE
    runtime_subjectivity_validator: Optional[str] = None
    captured_manifests: list[ArenaManifest] = []

    def capture_manifest(arena: ValidationArena) -> None:
        """Capture the exact arena instance before its first command."""
        if captured_manifests:
            raise RuntimeError("Self-play exposed more than one precombat arena manifest.")
        captured_manifests.append(build_arena_manifest(arena))

    try:
        with _match_deadline(match_timeout_seconds):
            result = run_external_selfplay(
                entry.arena_id,
                max_commands=max_commands,
                hero_first=entry.hero_first,
                random_seed=entry.random_seed,
                arena_observer=capture_manifest,
            )
        if len(captured_manifests) != 1:
            raise RuntimeError("Self-play did not expose exactly one precombat arena manifest.")
        manifest = captured_manifests[0]
        artifact = build_external_selfplay_artifact(
            result,
            run_id=(
                f"{match_id}-{entry.arena_id}"
                if attempt_number == 1
                else f"{match_id}-attempt-{attempt_number:04d}-{entry.arena_id}"
            ),
            random_seed=entry.random_seed,
        )
        runtime_policy_version = artifact.policy.version
        runtime_policy_source_hash = artifact.policy.source_hash
        runtime_controller_profile = artifact.controller_profile
        runtime_subjectivity_validator = artifact.subjectivity.validator
        artifact_path = _write_artifact_once(artifact, artifact_dir)
        artifact_paths.append(str(artifact_path))
        stream.append(
            event_type="ELO_MATCH_ARTIFACT_WRITTEN",
            matrix_id=schedule.matrix_id,
            match_id=match_id,
            match_index=entry.match_index,
            status="artifact_written",
            payload={"path": str(artifact_path)},
        )
        base_record = build_tournament_match_record(
            result,
            match_id=match_id,
            random_seed=entry.random_seed,
            hero_first=entry.hero_first,
            ratings={},
            elo_config=elo_config,
            run_artifact_path=str(artifact_path),
        )
        participants = build_match_participants(
            manifest=manifest,
            controller_profile=entry.controller_profile,
            policy_version=entry.policy_version,
        )
        eligibility = audit_evaluator_rating_eligibility(
            base_record,
            manifest=manifest,
            participants=participants,
            artifact_paths=artifact_paths,
            expected_policy_version=entry.policy_version,
            runtime_policy_version=artifact.policy.version,
            expected_controller_profile=entry.controller_profile,
            runtime_controller_profile=artifact.controller_profile,
            runtime_subjectivity_validator=artifact.subjectivity.validator,
        )
        updates = {}
        if eligibility.rating_eligible:
            updates = ledger_book.update_from_match(
                match_index=entry.match_index,
                match_id=match_id,
                outcome=base_record.outcome,
                participants=participants,
            )
            stream.append(
                event_type="ELO_RATINGS_UPDATED",
                matrix_id=schedule.matrix_id,
                match_id=match_id,
                match_index=entry.match_index,
                status="ratings_updated",
                payload={"ledgers": sorted(updates)},
            )
        else:
            ledger_book.record_skip(participants)
            stream.append(
                event_type="ELO_MATCH_SKIPPED_FROM_RATING",
                matrix_id=schedule.matrix_id,
                match_id=match_id,
                match_index=entry.match_index,
                status="rating_skipped",
                payload={"reasons": eligibility.reasons},
            )
        record = EloMatchRecord(
            match_id=match_id,
            match_index=entry.match_index,
            attempt_number=attempt_number,
            runtime_policy_version=runtime_policy_version,
            runtime_policy_source_hash=runtime_policy_source_hash,
            runtime_controller_profile=runtime_controller_profile,
            runtime_subjectivity_validator=runtime_subjectivity_validator,
            schedule_entry=entry,
            arena_manifest=manifest,
            base_record=base_record,
            participants=participants,
            eligibility=eligibility,
            rating_updates_by_ledger=updates,
            artifact_paths=artifact_paths,
            friction_flags=_friction_flags(base_record, eligibility),
            policy_trace_summary=_policy_trace_summary(artifact),
        )
        stream.append(
            event_type="ELO_MATCH_COMPLETED",
            matrix_id=schedule.matrix_id,
            match_id=match_id,
            match_index=entry.match_index,
            status=base_record.status,
            payload={"outcome": base_record.outcome, "eligible": eligibility.rating_eligible},
        )
        return record
    except Exception as exc:
        if manifest is None and len(captured_manifests) == 1:
            manifest = captured_manifests[0]
        timed_out = isinstance(exc, EloMatchTimeoutError)
        failure_status = "timeout" if timed_out else "crashed"
        failure = EloMatchFailureArtifact(
            matrix_id=schedule.matrix_id,
            match_id=match_id,
            match_index=entry.match_index,
            attempt_number=attempt_number,
            generated_at=_utc_now(),
            status=failure_status,
            exception_type=type(exc).__name__,
            message=str(exc),
            traceback="".join(traceback_module.format_exception(type(exc), exc, exc.__traceback__)),
            elapsed_ms=round((time.perf_counter() - entry_started) * 1000, 3),
            max_commands=max_commands,
            timeout_seconds=match_timeout_seconds,
            schedule_entry=entry,
            arena_manifest=manifest,
            runtime_policy_version=runtime_policy_version,
            runtime_policy_source_hash=runtime_policy_source_hash,
            runtime_controller_profile=runtime_controller_profile,
        )
        failure_path = _write_failure_artifact_once(failure, artifact_dir)
        artifact_paths.append(str(failure_path))
        stream.append(
            event_type="ELO_MATCH_ARTIFACT_WRITTEN",
            matrix_id=schedule.matrix_id,
            match_id=match_id,
            match_index=entry.match_index,
            status=f"{failure_status}_artifact_written",
            payload={"path": str(failure_path), "artifact_kind": "failure"},
        )
        eligibility = EloEligibility(
            status="skipped",
            rating_eligible=False,
            reasons=[f"{failure_status}:{type(exc).__name__}"],
            subjectivity_status="not_run",
            runner_status=failure_status,
            command_status_counts={},
            encounter_finished=False,
            command_cap_reached=False,
            crashed=not timed_out,
            timed_out=timed_out,
            has_unknown_outcome=True,
        )
        participants = (
            build_match_participants(
                manifest=manifest,
                controller_profile=entry.controller_profile,
                policy_version=entry.policy_version,
            )
            if manifest is not None
            else []
        )
        ledger_book.record_skip(participants)
        record = EloMatchRecord(
            match_id=match_id,
            match_index=entry.match_index,
            attempt_number=attempt_number,
            runtime_policy_version=runtime_policy_version,
            runtime_policy_source_hash=runtime_policy_source_hash,
            runtime_controller_profile=runtime_controller_profile,
            runtime_subjectivity_validator=runtime_subjectivity_validator,
            schedule_entry=entry,
            arena_manifest=manifest,
            base_record=None,
            participants=participants,
            eligibility=eligibility,
            artifact_paths=artifact_paths,
            friction_flags=[failure_status, type(exc).__name__],
            policy_trace_summary={"exception": str(exc)},
        )
        stream.append(
            event_type="ELO_MATCH_SKIPPED_FROM_RATING",
            matrix_id=schedule.matrix_id,
            match_id=match_id,
            match_index=entry.match_index,
            status=failure_status,
            message=str(exc),
            payload={"exception_type": type(exc).__name__},
        )
        return record


def _replay_record_into_ledgers(ledger_book: EloLedgerBook, record: EloMatchRecord) -> None:
    if record.eligibility.rating_eligible and record.base_record is not None:
        updates = ledger_book.update_from_match(
            match_index=record.match_index,
            match_id=record.match_id,
            outcome=record.base_record.outcome,
            participants=record.participants,
        )
        record.rating_updates_by_ledger.clear()
        record.rating_updates_by_ledger.update(updates)
    else:
        ledger_book.record_skip(record.participants)


def _rebuild_ledgers(records: list[EloMatchRecord], config: EloConfig) -> EloLedgerBook:
    """Rebuild every rating ledger in exact schedule order."""
    ledger_book = EloLedgerBook(elo_config=config)
    for record in sorted(records, key=lambda row: row.match_index):
        _replay_record_into_ledgers(ledger_book, record)
    return ledger_book


def _build_summary(
    *,
    schedule: EloMatrixSchedule,
    records: list[EloMatchRecord],
    ledger_book: EloLedgerBook,
    events: list[EloGauntletEvent],
    generated_at: str,
) -> EloGauntletSummary:
    completed_count = len(records)
    eligible_count = sum(1 for record in records if record.eligibility.rating_eligible)
    skipped_count = completed_count - eligible_count
    failed_count = sum(1 for record in records if not _is_clean_match(record))
    pending_count = len(schedule.entries) - completed_count
    gate_reasons = _gate_reasons(
        pending_count=pending_count,
        failed_count=failed_count,
        skipped_count=skipped_count,
    )
    summary = EloGauntletSummary(
        matrix_id=schedule.matrix_id,
        mode=schedule.mode,
        generated_at=generated_at,
        schedule_hash=schedule.schedule_hash,
        arena_catalog_hash=schedule.arena_catalog_hash,
        policy_catalog_hash=schedule.policy_catalog_hash,
        scheduled_count=len(schedule.entries),
        completed_count=completed_count,
        eligible_count=eligible_count,
        skipped_rating_count=skipped_count,
        failed_count=failed_count,
        pending_count=pending_count,
        completion_status="completed" if pending_count == 0 else "partial" if completed_count else "not_run",
        gate_status="passed" if not gate_reasons else "failed",
        gate_reasons=gate_reasons,
        schedule=schedule,
        matches=records,
        ledgers=ledger_book.ledgers(),
        failure_rows=_failure_rows(records),
        subjectivity_summary=_subjectivity_summary(records),
        performance=_performance_summary(
            records,
            evaluation_started_at=schedule.created_at,
            evaluation_completed_at=generated_at,
        ),
        coverage=_coverage_summary(schedule, records),
        dashboard_projection={},
        events=events,
    )
    return summary.model_copy(update={"dashboard_projection": project_elo_dashboard(summary)})


def _build_checkpoint(
    *,
    schedule: EloMatrixSchedule,
    records: list[EloMatchRecord],
    generated_at: str,
) -> EloGauntletCheckpoint:
    """Build compact progress metadata backed by per-match records."""
    completed_count = len(records)
    eligible_count = sum(1 for record in records if record.eligibility.rating_eligible)
    skipped_count = completed_count - eligible_count
    failed_count = sum(1 for record in records if not _is_clean_match(record))
    pending_count = len(schedule.entries) - completed_count
    gate_reasons = _gate_reasons(
        pending_count=pending_count,
        failed_count=failed_count,
        skipped_count=skipped_count,
    )
    return EloGauntletCheckpoint(
        matrix_id=schedule.matrix_id,
        generated_at=generated_at,
        schedule_hash=schedule.schedule_hash,
        scheduled_count=len(schedule.entries),
        completed_count=completed_count,
        eligible_count=eligible_count,
        skipped_rating_count=skipped_count,
        failed_count=failed_count,
        pending_count=pending_count,
        completion_status="completed" if pending_count == 0 else "partial" if completed_count else "not_run",
        gate_status="passed" if not gate_reasons else "failed",
        gate_reasons=gate_reasons,
        completed_match_indices=[record.match_index for record in records],
        latest_match_id=records[-1].match_id if records else None,
    )


def _load_resume_records(schedule: EloMatrixSchedule, matrix_dir: Path) -> list[EloMatchRecord]:
    retained_schedule_path = matrix_dir / "schedule.json"
    if retained_schedule_path.exists():
        retained_schedule = load_elo_matrix_schedule(retained_schedule_path)
        if retained_schedule.matrix_id != schedule.matrix_id:
            raise ValueError("Cannot resume Elo matrix: matrix id mismatch")
        if retained_schedule.schedule_hash != schedule.schedule_hash:
            raise ValueError("Cannot resume Elo matrix: schedule hash mismatch")

    match_paths = sorted((matrix_dir / "matches").glob("*.json"))
    if match_paths:
        expected_by_index = {entry.match_index: entry for entry in schedule.entries}
        records: list[EloMatchRecord] = []
        seen_indices: set[int] = set()
        for path in match_paths:
            record = EloMatchRecord.model_validate_json(path.read_text(encoding="utf-8"))
            expected = expected_by_index.get(record.match_index)
            if expected is None:
                raise ValueError(f"Cannot resume Elo matrix: unexpected match index {record.match_index}")
            if record.match_index in seen_indices:
                raise ValueError(f"Cannot resume Elo matrix: duplicate match index {record.match_index}")
            if record.schedule_entry != expected:
                raise ValueError(f"Cannot resume Elo matrix: schedule row mismatch at index {record.match_index}")
            seen_indices.add(record.match_index)
            records.append(record)
        return sorted(records, key=lambda row: row.match_index)

    # Compatibility with checkpoints written before per-match records became
    # the authoritative resume source.
    checkpoint = matrix_dir / "checkpoints" / "latest.partial.json"
    summary_path = matrix_dir / "summary.json"
    source = checkpoint if checkpoint.exists() else summary_path
    if not source.exists():
        return []
    summary = EloGauntletSummary.model_validate_json(source.read_text(encoding="utf-8"))
    if summary.schedule_hash != schedule.schedule_hash:
        raise ValueError("Cannot resume Elo matrix: schedule hash mismatch")
    return list(summary.matches)


def load_elo_matrix_schedule(path: Path | str) -> EloMatrixSchedule:
    """Load a retained matrix schedule without generating a new matrix id."""
    source = Path(path)
    return EloMatrixSchedule.model_validate_json(source.read_text(encoding="utf-8"))


def refresh_elo_summary(path: Path | str) -> EloGauntletSummary:
    """Rebuild derived performance and dashboard data from retained evidence.

    Args:
        path: Matrix-local ``summary.json`` or root ``latest.json`` path.

    Returns:
        Refreshed and atomically persisted summary.
    """
    source = Path(path)
    summary = EloGauntletSummary.model_validate_json(source.read_text(encoding="utf-8"))
    setup_ledger = summary.ledgers.get("setup_side")
    elo_config = setup_ledger.elo_config if setup_ledger is not None else EloConfig()
    records = list(summary.matches)
    ledger_book = _rebuild_ledgers(records, elo_config)
    refreshed = summary.model_copy(update={
        "matches": records,
        "ledgers": ledger_book.ledgers(),
        "performance": _performance_summary(
            records,
            evaluation_started_at=summary.schedule.created_at,
            evaluation_completed_at=summary.generated_at,
        ),
        "subjectivity_summary": _subjectivity_summary(records),
        "dashboard_projection": {},
    })
    refreshed = refreshed.model_copy(update={
        "dashboard_projection": project_elo_dashboard(refreshed),
    })
    if source.parent.name == summary.matrix_id:
        matrix_dir = source.parent
    else:
        matrix_dir = source.parent / summary.matrix_id
    root = matrix_dir.parent
    _write_final_summary(refreshed, root, matrix_dir)
    return refreshed


def _write_artifact_once(artifact: ValidationRunArtifact, artifact_dir: Path) -> Path:
    try:
        return write_validation_run_artifact(artifact, artifact_dir)
    except FileExistsError:
        for recovery_number in range(2, 10_000):
            recovery = artifact.model_copy(update={
                "run_id": f"{artifact.run_id}-recovery-{recovery_number:04d}",
            })
            try:
                return write_validation_run_artifact(recovery, artifact_dir)
            except FileExistsError:
                continue
        raise RuntimeError(f"Unable to allocate a recovery artifact id for {artifact.run_id}")


def _write_failure_artifact_once(
    artifact: EloMatchFailureArtifact,
    artifact_dir: Path,
) -> Path:
    """Write a crash/timeout artifact without replacing prior evidence."""
    artifact_dir.mkdir(parents=True, exist_ok=True)
    stem = f"{artifact.match_id}-attempt-{artifact.attempt_number:04d}"
    for recovery_number in range(1, 10_000):
        suffix = "" if recovery_number == 1 else f"-recovery-{recovery_number:04d}"
        path = artifact_dir / f"{stem}{suffix}.failure.json"
        if path.exists():
            continue
        _write_json(path, artifact.model_dump(mode="json"))
        return path
    raise RuntimeError(f"Unable to allocate a failure artifact path for {artifact.match_id}")


def _archive_match_attempt(matrix_dir: Path, record: EloMatchRecord) -> Path:
    """Archive the current canonical record before a retained row is retried."""
    path = (
        matrix_dir
        / "attempts"
        / record.match_id
        / f"attempt-{record.attempt_number:04d}.match.json"
    )
    if not path.exists():
        _write_json(path, record.model_dump(mode="json"))
    return path


def _validate_retry_policy_identity(schedule: EloMatrixSchedule) -> None:
    """Prevent behavioral fixes from being mixed into an older policy matrix."""
    scheduled_versions = {entry.policy_version for entry in schedule.entries}
    scheduled_profiles = {entry.controller_profile for entry in schedule.entries}
    if scheduled_versions != {POLICY_VERSION} or scheduled_profiles != {CONTROLLER_PROFILE}:
        rendered = ", ".join(sorted(version or "unversioned" for version in scheduled_versions))
        rendered_profiles = ", ".join(sorted(scheduled_profiles))
        raise ValueError(
            "Cannot retry Elo rows under a different policy identity: "
            f"schedule_policy={rendered}, runtime_policy={POLICY_VERSION}, "
            f"schedule_controller={rendered_profiles}, runtime_controller={CONTROLLER_PROFILE}. "
            "Build a new schedule instead."
        )


def _write_match_records(matches_dir: Path, records: list[EloMatchRecord]) -> None:
    """Persist final schedule-ordered rating updates into canonical row files."""
    for record in records:
        _write_json(matches_dir / f"{record.match_id}.json", record.model_dump(mode="json"))


def _write_final_summary(summary: EloGauntletSummary, root: Path, matrix_dir: Path) -> None:
    validate_elo_summary(summary)
    summary_path = matrix_dir / "summary.json"
    _write_json(summary_path, summary.model_dump(mode="json"))
    _copy_file_atomic(summary_path, root / "latest.json")
    _write_json(matrix_dir / "dashboard.json", summary.dashboard_projection)
    _copy_file_atomic(matrix_dir / "dashboard.json", root / "latest.dashboard.json")


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=True, default=str)
        handle.write("\n")
    temporary.replace(path)


def _copy_file_atomic(source: Path, destination: Path) -> None:
    """Copy one retained artifact through an atomic destination replacement."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(f".{destination.name}.tmp")
    shutil.copyfile(source, temporary)
    temporary.replace(destination)


def _match_id(schedule: EloMatrixSchedule, entry: EloMatrixScheduleEntry) -> str:
    return f"{schedule.matrix_id}-{entry.match_index:04d}"


def _is_clean_match(record: EloMatchRecord) -> bool:
    return record.eligibility.rating_eligible and record.base_record is not None


def _gate_reasons(*, pending_count: int, failed_count: int, skipped_count: int) -> list[str]:
    reasons: list[str] = []
    if pending_count:
        reasons.append("pending_rows")
    if failed_count:
        reasons.append("failed_or_abnormal_rows")
    if skipped_count:
        reasons.append("rating_skipped_rows")
    return reasons


def _failure_rows(records: list[EloMatchRecord]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for record in records:
        if _is_clean_match(record):
            continue
        rows.append({
            "match_id": record.match_id,
            "match_index": record.match_index,
            "arena_id": record.schedule_entry.arena_id,
            "status": record.base_record.status if record.base_record is not None else record.eligibility.runner_status,
            "outcome": record.base_record.outcome if record.base_record is not None else "unknown",
            "reasons": list(record.eligibility.reasons),
            "artifact_paths": list(record.artifact_paths),
        })
    return rows


def _subjectivity_summary(records: list[EloMatchRecord]) -> dict[str, Any]:
    counts: Counter[str] = Counter()
    validator_counts: Counter[str] = Counter()
    violation_count = 0
    violation_matches: list[str] = []
    for record in records:
        status = record.eligibility.subjectivity_status
        counts[status] += 1
        validator_counts[record.runtime_subjectivity_validator or "missing"] += 1
        if record.base_record is not None:
            violation_count += record.base_record.subjectivity_violation_count
            if record.base_record.subjectivity_violation_count:
                violation_matches.append(record.match_id)
    return {
        "status_counts": dict(sorted(counts.items())),
        "validator_counts": dict(sorted(validator_counts.items())),
        "violation_count": violation_count,
        "violation_match_ids": violation_matches,
    }


def _performance_summary(
    records: list[EloMatchRecord],
    *,
    evaluation_started_at: Optional[str] = None,
    evaluation_completed_at: Optional[str] = None,
) -> dict[str, Any]:
    return analyze_elo_performance(
        records,
        evaluation_started_at=evaluation_started_at,
        evaluation_completed_at=evaluation_completed_at,
    ).model_dump(mode="json")


def _coverage_summary(schedule: EloMatrixSchedule, records: list[EloMatchRecord]) -> EloCoverageSummary:
    scheduled_arenas = sorted({entry.arena_id for entry in schedule.entries})
    completed_arenas = sorted({record.schedule_entry.arena_id for record in records})
    side_counts = Counter(record.schedule_entry.side_order_id for record in records)
    roster_hashes = sorted({
        roster_hash
        for record in records
        if record.arena_manifest is not None
        for roster_hash in record.arena_manifest.roster_hash_by_side.values()
    })
    tags = sorted({tag for entry in schedule.entries for tag in entry.tags})
    return EloCoverageSummary(
        arena_ids_scheduled=scheduled_arenas,
        arena_ids_completed=completed_arenas,
        arena_ids_missing=sorted(set(scheduled_arenas) - set(completed_arenas)),
        seeds_scheduled=sorted({entry.random_seed for entry in schedule.entries}),
        side_orders_scheduled=sorted({entry.side_order_id for entry in schedule.entries}),
        side_order_counts=dict(sorted(side_counts.items())),
        tags_covered=tags,
        roster_hashes_covered=roster_hashes,
    )


def _friction_flags(record: TournamentMatchRecord, eligibility: EloEligibility) -> list[str]:
    flags = list(eligibility.reasons)
    if record.command_count == 0:
        flags.append("no_commands")
    if record.outcome == "draw":
        flags.append("draw")
    return sorted(set(flags))


def _policy_trace_summary(artifact: ValidationRunArtifact) -> dict[str, Any]:
    """Aggregate the retained raw policy trace without inventing decisions."""
    semantic_counts: Counter[str] = Counter()
    routine_counts: Counter[str] = Counter()
    command_status_counts: Counter[str] = Counter()
    outcome_tag_counts: Counter[str] = Counter()
    selected_rows: Counter[str] = Counter()
    for trace in artifact.result.traces:
        if trace.semantic_key:
            semantic_counts[trace.semantic_key] += 1
        if trace.routine_id:
            routine_counts[trace.routine_id] += 1
        if trace.command_status:
            command_status_counts[trace.command_status] += 1
        if trace.row_id:
            selected_rows[trace.row_id] += 1
        outcome_tag_counts.update(trace.outcome_logical_tags)
    return {
        "semantic_counts": dict(sorted(semantic_counts.items())),
        "routine_counts": dict(sorted(routine_counts.items())),
        "command_status_counts": dict(sorted(command_status_counts.items())),
        "outcome_tag_counts": dict(sorted(outcome_tag_counts.items())),
        "selected_row_counts": dict(sorted(selected_rows.items())),
    }


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _watcher_event_type(event_type: EloGauntletEventType) -> GauntletEventType:
    """Map evaluator detail events onto the shared gauntlet watcher vocabulary."""
    if event_type == "ELO_GAUNTLET_STARTED":
        return "GAUNTLET_STARTED"
    if event_type == "ELO_MATCH_STARTED":
        return "MATCH_STARTED"
    if event_type in {"ELO_MATCH_SKIPPED_FROM_RATING", "ELO_GAUNTLET_FAILED"}:
        return "MATCH_FAILED" if event_type == "ELO_MATCH_SKIPPED_FROM_RATING" else "GAUNTLET_COMPLETED"
    if event_type == "ELO_MATCH_COMPLETED":
        return "MATCH_COMPLETED"
    if event_type == "ELO_RATINGS_UPDATED":
        return "RATING_UPDATED"
    if event_type == "ELO_GAUNTLET_COMPLETED":
        return "GAUNTLET_COMPLETED"
    return "MATCH_PROGRESS"


@app.command("schedule")
def schedule_command(
    mode: EloMatrixMode = typer.Option("elo_matrix", "--mode"),
    arena_id: Optional[list[str]] = typer.Option(None, "--arena-id"),
    seed: Optional[list[int]] = typer.Option(None, "--seed"),
    side_order: Optional[list[str]] = typer.Option(None, "--side-order"),
    controller_profile: str = typer.Option(CONTROLLER_PROFILE, "--controller-profile"),
    policy_version: Optional[str] = typer.Option(None, "--policy-version"),
) -> None:
    """Print an Elo matrix schedule."""
    schedule = build_elo_matrix_schedule(
        mode=mode,
        arena_ids=arena_id,
        seeds=seed,
        side_orders=_parse_side_orders(side_order),
        controller_profile=controller_profile,
        policy_version=policy_version,
    )
    _emit(schedule.model_dump(mode="json"))


@app.command("run")
def run_command(
    mode: EloMatrixMode = typer.Option("elo_matrix", "--mode"),
    arena_id: Optional[list[str]] = typer.Option(None, "--arena-id"),
    seed: Optional[list[int]] = typer.Option(None, "--seed"),
    side_order: Optional[list[str]] = typer.Option(None, "--side-order"),
    controller_profile: str = typer.Option(CONTROLLER_PROFILE, "--controller-profile"),
    policy_version: Optional[str] = typer.Option(None, "--policy-version"),
    max_commands: int = typer.Option(240, "--max-commands", min=1),
    match_timeout_seconds: float = typer.Option(
        120.0,
        "--match-timeout-seconds",
        min=0.001,
        help="Interrupt and retain a failure artifact when one match exceeds this wall-clock deadline.",
    ),
    output_directory: Path = typer.Option(Path("ai/evidence/elo_gauntlets"), "--summary-output-directory"),
    runs_output_directory: Optional[Path] = typer.Option(None, "--runs-output-directory"),
    schedule_path: Optional[Path] = typer.Option(
        None,
        "--schedule-path",
        help="Resume an exact retained schedule instead of generating a new matrix id.",
    ),
    resume: bool = typer.Option(True, "--resume/--no-resume"),
    retry_ineligible: bool = typer.Option(
        False,
        "--retry-ineligible",
        help="Archive and rerun retained ineligible rows when the policy identity is unchanged.",
    ),
    require_complete: bool = typer.Option(False, "--require-complete"),
    require_rating_eligible: bool = typer.Option(False, "--require-rating-eligible"),
    watcher_base_url: Optional[str] = typer.Option(
        None,
        "--watcher-base-url",
        help="Backend URL that should receive live Elo gauntlet events.",
    ),
    json_output: bool = typer.Option(True, "--json/--no-json"),
) -> None:
    """Run an Elo matrix gauntlet."""
    schedule = (
        load_elo_matrix_schedule(schedule_path)
        if schedule_path is not None
        else build_elo_matrix_schedule(
            mode=mode,
            arena_ids=arena_id,
            seeds=seed,
            side_orders=_parse_side_orders(side_order),
            controller_profile=controller_profile,
            policy_version=policy_version,
        )
    )
    event_stream = HttpMirroringEloGauntletEventStream(watcher_base_url) if watcher_base_url else None
    try:
        summary = run_elo_gauntlet(
            schedule,
            max_commands=max_commands,
            match_timeout_seconds=match_timeout_seconds,
            runs_output_directory=runs_output_directory,
            summary_output_directory=output_directory,
            resume=resume,
            retry_ineligible=retry_ineligible,
            require_complete=require_complete,
            require_rating_eligible=require_rating_eligible,
            event_stream=event_stream,
        )
    finally:
        if event_stream is not None:
            event_stream.close()
    if json_output:
        _emit(summary.dashboard_projection)
    else:
        typer.echo(
            f"{summary.matrix_id}: {summary.completed_count}/{summary.scheduled_count} completed, "
            f"{summary.eligible_count} eligible, gate={summary.gate_status}"
        )


@app.command("summarize")
def summarize_command(path: Path) -> None:
    """Print a compact projection from a retained Elo summary."""
    summary = EloGauntletSummary.model_validate_json(path.read_text(encoding="utf-8"))
    _emit(summary.dashboard_projection)


@app.command("validate")
def validate_command(path: Path) -> None:
    """Validate a retained Elo summary."""
    summary = EloGauntletSummary.model_validate_json(path.read_text(encoding="utf-8"))
    validate_elo_summary(summary)
    _emit({"status": "passed", "matrix_id": summary.matrix_id})


@app.command("refresh")
def refresh_command(path: Path) -> None:
    """Rebuild derived performance/dashboard JSON from retained raw runs."""
    summary = refresh_elo_summary(path)
    _emit(summary.dashboard_projection)


def _emit(payload: object) -> None:
    typer.echo(json.dumps(payload, indent=2, ensure_ascii=True, default=str))


def _parse_side_orders(values: Optional[list[str]]) -> tuple[bool, ...]:
    """Parse repeatable CLI side-order labels into schedule booleans."""
    if not values:
        return DEFAULT_SIDE_ORDERS
    parsed: list[bool] = []
    aliases = {
        "hero-first": True,
        "hero_first": True,
        "monster-first": False,
        "monster_first": False,
    }
    for value in values:
        normalized = value.strip().lower()
        if normalized not in aliases:
            raise typer.BadParameter(
                "side order must be hero-first or monster-first",
                param_hint="--side-order",
            )
        parsed.append(aliases[normalized])
    return tuple(dict.fromkeys(parsed))


if __name__ == "__main__":
    app()
