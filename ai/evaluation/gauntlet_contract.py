"""Lightweight gauntlet watcher contracts.

This module is intentionally independent of self-play runners and server state.
"""

from __future__ import annotations

import math
from typing import Any, Iterable, Literal, Optional, Protocol, cast

from pydantic import BaseModel, Field

GauntletMode = Literal["smoke", "rotation", "content", "regression", "release"]
GauntletGateStatus = Literal["not_run", "running", "passed", "failed"]
GauntletLatencyStatus = Literal["not_run", "passed", "failed"]
GAUNTLET_COMMAND_TOTAL_P95_TARGET_MS = 5.0
GAUNTLET_COMMAND_TOTAL_P99_TARGET_MS = 10.0
GAUNTLET_LOCAL_DECISION_P99_TARGET_MS = 5.0
GAUNTLET_LEGACY_MAX_COMMAND_TOTAL_TARGET_MS = 10.0
GAUNTLET_LEGACY_MAX_LOCAL_DECISION_TARGET_MS = 5.0
GauntletEventType = Literal[
    "GAUNTLET_STARTED",
    "MATCH_STARTED",
    "MATCH_PROGRESS",
    "MATCH_COMPLETED",
    "MATCH_FAILED",
    "RATING_UPDATED",
    "SUMMARY_WRITTEN",
    "GAUNTLET_COMPLETED",
]


class GauntletEvent(BaseModel):
    """Cursor-addressed watcher event for gauntlet progress."""

    cursor: int = Field(description="Monotonic event cursor within this gauntlet.")
    event_type: GauntletEventType = Field(description="Watcher event type.")
    gauntlet_id: str = Field(description="Gauntlet id.")
    match_id: Optional[str] = Field(default=None, description="Related match id when present.")
    match_index: Optional[int] = Field(default=None, description="Related schedule index when present.")
    status: Optional[str] = Field(default=None, description="Compact event status.")
    message: Optional[str] = Field(default=None, description="Human-readable watcher message.")
    payload: dict[str, object] = Field(default_factory=dict, description="Typed summary payload for watcher projection.")
    created_at: str = Field(description="UTC timestamp when the event was created.")


class GauntletEventIngestRequest(BaseModel):
    """Batch of externally produced watcher events to publish."""

    events: list[GauntletEvent] = Field(default_factory=list, description="Watcher events to publish.")


class GauntletSummary(BaseModel):
    """Compact JSON summary consumed by gauntlet dashboards and watchers."""

    schema_version: Literal[1] = Field(default=1, description="Gauntlet summary schema version.")
    gauntlet_id: str = Field(description="Stable gauntlet batch id.")
    mode: GauntletMode = Field(description="Gauntlet mode.")
    generated_at: str = Field(description="UTC timestamp when the summary was generated.")
    schedule_hash: str = Field(description="Hash of the schedule used for this summary.")
    schedule: list[Any] = Field(default_factory=list, description="Schedule rows used by this gauntlet.")
    matches: list[Any] = Field(default_factory=list, description="Completed or failed match records.")
    ratings: dict[str, float] = Field(default_factory=dict, description="Final ratings keyed by participant id.")
    rating_series: list[Any] = Field(default_factory=list, description="Rating time series.")
    events: list[GauntletEvent] = Field(default_factory=list, description="Watcher event history snapshot.")
    status_counts: dict[str, int] = Field(default_factory=dict, description="Match count by runner status.")
    outcome_counts: dict[str, int] = Field(default_factory=dict, description="Match count by inferred outcome.")
    command_status_counts: dict[str, int] = Field(default_factory=dict, description="Command-result counts aggregated from match records.")
    performance: Optional["GauntletPerformanceSummary"] = Field(default=None, description="Batch-level command and timing summary.")
    artifact_paths: list[str] = Field(default_factory=list, description="Raw match artifact paths retained by the gauntlet.")
    failure_rows: list["GauntletFailureRow"] = Field(default_factory=list, description="Visible failed or abnormal match rows.")
    subjectivity_status: Literal["not_run", "passed", "failed"] = Field(default="not_run", description="Batch subjectivity status.")
    subjectivity_violation_count: int = Field(default=0, description="Total disclosure audit violations across retained match records.")
    gate_status: GauntletGateStatus = Field(default="not_run", description="Release-gate status derived from retained summary evidence.")
    gate_reasons: list[str] = Field(default_factory=list, description="Machine-readable reasons preventing this batch from passing the gate.")
    latency_status: GauntletLatencyStatus = Field(default="not_run", description="Whether retained command latency evidence meets the interactive target.")
    latency_reasons: list[str] = Field(default_factory=list, description="Machine-readable latency audit failures.")
    latency_thresholds: dict[str, float] = Field(
        default_factory=lambda: {
            "command_total_p95_ms": GAUNTLET_COMMAND_TOTAL_P95_TARGET_MS,
            "command_total_p99_ms": GAUNTLET_COMMAND_TOTAL_P99_TARGET_MS,
            "local_decision_p99_ms": GAUNTLET_LOCAL_DECISION_P99_TARGET_MS,
            "legacy_max_command_total_ms": GAUNTLET_LEGACY_MAX_COMMAND_TOTAL_TARGET_MS,
            "legacy_max_local_decision_ms": GAUNTLET_LEGACY_MAX_LOCAL_DECISION_TARGET_MS,
        },
        description="Latency thresholds used by the retained evidence audit.",
    )
    completed_count: int = Field(default=0, description="Matches that completed normally.")
    failed_count: int = Field(default=0, description="Matches that did not complete normally.")
    pending_count: int = Field(default=0, description="Scheduled matches without a record.")
    failed_match_ids: list[str] = Field(default_factory=list, description="Failed or abnormal match ids.")
    subjectivity_violation_match_ids: list[str] = Field(default_factory=list, description="Matches with detected subjectivity violations.")


class GauntletLatencyStageSummary(BaseModel):
    """Aggregate latency evidence for one named command stage."""

    sample_count: int = Field(description="Number of retained samples for this stage.")
    mean_ms: Optional[float] = Field(default=None, description="Mean latency for this stage.")
    p95_ms: Optional[float] = Field(default=None, description="Nearest-rank p95 latency for this stage.")
    p99_ms: Optional[float] = Field(default=None, description="Nearest-rank p99 latency for this stage.")
    max_ms: Optional[float] = Field(default=None, description="Largest retained latency for this stage.")


class GauntletPerformanceSummary(BaseModel):
    """Batch-level command and timing summary for a gauntlet."""

    match_count: int = Field(description="Number of match records included.")
    total_command_count: int = Field(description="Total commands across retained match records.")
    average_command_count: Optional[float] = Field(default=None, description="Mean commands per retained match.")
    total_elapsed_ms: float = Field(description="Total recorded match runtime in milliseconds.")
    average_elapsed_ms: Optional[float] = Field(default=None, description="Mean recorded match runtime in milliseconds.")
    max_elapsed_ms: Optional[float] = Field(default=None, description="Largest recorded match runtime in milliseconds.")
    max_command_total_ms: Optional[float] = Field(default=None, description="Largest traced per-command total latency.")
    max_server_command_ms: Optional[float] = Field(default=None, description="Largest traced server-side command latency.")
    max_local_decision_ms: Optional[float] = Field(default=None, description="Largest traced local decision latency.")
    command_total_sample_count: int = Field(default=0, description="Number of retained total command latency samples.")
    server_command_sample_count: int = Field(default=0, description="Number of retained server command latency samples.")
    local_decision_sample_count: int = Field(default=0, description="Number of retained local decision latency samples.")
    normal_command_total_sample_count: int = Field(default=0, description="Number of non-diagnostic total command latency samples.")
    normal_server_command_sample_count: int = Field(default=0, description="Number of non-diagnostic server command latency samples.")
    normal_local_decision_sample_count: int = Field(default=0, description="Number of non-diagnostic local decision latency samples.")
    diagnostic_command_total_sample_count: int = Field(default=0, description="Number of diagnostic total command latency samples.")
    diagnostic_server_command_sample_count: int = Field(default=0, description="Number of diagnostic server command latency samples.")
    diagnostic_local_decision_sample_count: int = Field(default=0, description="Number of diagnostic local decision latency samples.")
    command_total_p95_ms: Optional[float] = Field(default=None, description="Nearest-rank p95 total command latency.")
    command_total_p99_ms: Optional[float] = Field(default=None, description="Nearest-rank p99 total command latency.")
    server_command_p95_ms: Optional[float] = Field(default=None, description="Nearest-rank p95 server command latency.")
    server_command_p99_ms: Optional[float] = Field(default=None, description="Nearest-rank p99 server command latency.")
    local_decision_p95_ms: Optional[float] = Field(default=None, description="Nearest-rank p95 local decision latency.")
    local_decision_p99_ms: Optional[float] = Field(default=None, description="Nearest-rank p99 local decision latency.")
    normal_command_total_p95_ms: Optional[float] = Field(default=None, description="Nearest-rank p95 total latency for non-diagnostic commands.")
    normal_command_total_p99_ms: Optional[float] = Field(default=None, description="Nearest-rank p99 total latency for non-diagnostic commands.")
    normal_server_command_p95_ms: Optional[float] = Field(default=None, description="Nearest-rank p95 server latency for non-diagnostic commands.")
    normal_server_command_p99_ms: Optional[float] = Field(default=None, description="Nearest-rank p99 server latency for non-diagnostic commands.")
    normal_local_decision_p95_ms: Optional[float] = Field(default=None, description="Nearest-rank p95 local decision latency for non-diagnostic commands.")
    normal_local_decision_p99_ms: Optional[float] = Field(default=None, description="Nearest-rank p99 local decision latency for non-diagnostic commands.")
    diagnostic_command_total_p95_ms: Optional[float] = Field(default=None, description="Nearest-rank p95 total latency for diagnostic commands.")
    diagnostic_command_total_p99_ms: Optional[float] = Field(default=None, description="Nearest-rank p99 total latency for diagnostic commands.")
    diagnostic_server_command_p95_ms: Optional[float] = Field(default=None, description="Nearest-rank p95 server latency for diagnostic commands.")
    diagnostic_server_command_p99_ms: Optional[float] = Field(default=None, description="Nearest-rank p99 server latency for diagnostic commands.")
    diagnostic_local_decision_p95_ms: Optional[float] = Field(default=None, description="Nearest-rank p95 local decision latency for diagnostic commands.")
    diagnostic_local_decision_p99_ms: Optional[float] = Field(default=None, description="Nearest-rank p99 local decision latency for diagnostic commands.")
    max_normal_command_total_ms: Optional[float] = Field(default=None, description="Largest non-diagnostic total command latency.")
    max_normal_server_command_ms: Optional[float] = Field(default=None, description="Largest non-diagnostic server command latency.")
    max_normal_local_decision_ms: Optional[float] = Field(default=None, description="Largest non-diagnostic local decision latency.")
    max_diagnostic_command_total_ms: Optional[float] = Field(default=None, description="Largest diagnostic total command latency.")
    max_diagnostic_server_command_ms: Optional[float] = Field(default=None, description="Largest diagnostic server command latency.")
    max_diagnostic_local_decision_ms: Optional[float] = Field(default=None, description="Largest diagnostic local decision latency.")
    stages: dict[str, GauntletLatencyStageSummary] = Field(
        default_factory=dict,
        description="Per-stage latency summaries across all retained command traces.",
    )
    normal_stages: dict[str, GauntletLatencyStageSummary] = Field(
        default_factory=dict,
        description="Per-stage latency summaries for non-diagnostic command traces.",
    )
    diagnostic_stages: dict[str, GauntletLatencyStageSummary] = Field(
        default_factory=dict,
        description="Per-stage latency summaries for diagnostic command traces.",
    )


class GauntletFailureRow(BaseModel):
    """Visible failed or abnormal match row for watcher and release gates."""

    match_id: str = Field(description="Failed or abnormal match id.")
    match_index: Optional[int] = Field(default=None, description="Schedule index if known.")
    arena_id: Optional[str] = Field(default=None, description="Arena id if known.")
    status: str = Field(description="Runner status.")
    outcome: Optional[str] = Field(default=None, description="Match outcome when available.")
    reason: Optional[str] = Field(default=None, description="Compact failure reason for watcher display.")
    run_artifact_path: Optional[str] = Field(default=None, description="Raw run artifact path when retained.")


class GauntletWatcherState(BaseModel):
    """Current watcher projection derived from summary JSON plus event stream."""

    gauntlet_id: str = Field(description="Gauntlet id.")
    mode: GauntletMode = Field(description="Gauntlet mode.")
    status: str = Field(description="Current watcher status.")
    active_match_id: Optional[str] = Field(default=None, description="Currently running match id if known.")
    active_match_index: Optional[int] = Field(default=None, description="Currently running match index if known.")
    completed_count: int = Field(description="Completed match count.")
    failed_count: int = Field(description="Failed match count.")
    pending_count: int = Field(description="Pending match count.")
    latest_outcome: Optional[str] = Field(default=None, description="Most recent match outcome.")
    latest_failure: Optional[str] = Field(default=None, description="Most recent failure message.")
    ratings: dict[str, float] = Field(default_factory=dict, description="Current rating table.")
    rating_series: list[Any] = Field(default_factory=list, description="Rating time series.")
    status_counts: dict[str, int] = Field(default_factory=dict, description="Match count by runner status.")
    outcome_counts: dict[str, int] = Field(default_factory=dict, description="Match count by inferred outcome.")
    command_status_counts: dict[str, int] = Field(default_factory=dict, description="Command-result counts aggregated from match records.")
    performance: Optional[GauntletPerformanceSummary] = Field(default=None, description="Batch-level command and timing summary.")
    artifact_paths: list[str] = Field(default_factory=list, description="Raw match artifact paths retained by the gauntlet.")
    failure_rows: list[GauntletFailureRow] = Field(default_factory=list, description="Visible failed or abnormal match rows.")
    subjectivity_status: Literal["not_run", "passed", "failed"] = Field(default="not_run", description="Batch subjectivity status.")
    subjectivity_violation_count: int = Field(default=0, description="Total disclosure audit violations across retained match records.")
    gate_status: GauntletGateStatus = Field(default="not_run", description="Release-gate status derived from retained summary evidence.")
    gate_reasons: list[str] = Field(default_factory=list, description="Machine-readable reasons preventing this batch from passing the gate.")
    latency_status: GauntletLatencyStatus = Field(default="not_run", description="Whether retained command latency evidence meets the interactive target.")
    latency_reasons: list[str] = Field(default_factory=list, description="Machine-readable latency audit failures.")
    latency_thresholds: dict[str, float] = Field(default_factory=dict, description="Latency thresholds used by the retained evidence audit.")
    subjectivity_violation_match_ids: list[str] = Field(default_factory=list, description="Subjectivity violation match ids.")
    recent_events: list[GauntletEvent] = Field(default_factory=list, description="Recent watcher events.")


class GauntletEventSink(Protocol):
    """Minimal event contract shared by gauntlet runners and live watchers."""

    def append(
        self,
        *,
        event_type: GauntletEventType,
        gauntlet_id: str,
        match_id: Optional[str] = None,
        match_index: Optional[int] = None,
        status: Optional[str] = None,
        message: Optional[str] = None,
        payload: Optional[dict[str, object]] = None,
    ) -> GauntletEvent:
        """Append one watcher event."""
        ...

    def since(self, cursor: int = 0) -> list[GauntletEvent]:
        """Return retained events after a cursor."""
        ...


def validate_gauntlet_summary_evidence(summary: GauntletSummary) -> GauntletSummary:
    """Reject retained gauntlet summaries whose audit metadata contradicts rows."""
    matches = list(summary.matches)
    schedule = list(summary.schedule)
    failed_ids = [
        str(_get_raw_value(match, "match_id"))
        for match in matches
        if _gauntlet_abnormal_reason(match) is not None
    ]
    subjectivity_ids = [
        str(_get_raw_value(match, "match_id"))
        for match in matches
        if _match_has_subjectivity_violation(match)
    ]
    command_status_counts = _sum_command_status_counts(matches)
    subjectivity_violation_count = sum(_get_int(match, "subjectivity_violation_count") for match in matches)

    if summary.completed_count + summary.failed_count != len(matches):
        raise ValueError("Gauntlet completed/failed counts do not match retained matches.")
    if summary.failed_count != len(failed_ids):
        raise ValueError("Gauntlet failed count does not match abnormal retained matches.")
    if schedule and summary.completed_count + summary.failed_count + summary.pending_count != len(schedule):
        raise ValueError("Gauntlet pending count does not match schedule size.")
    if sorted(summary.failed_match_ids) != sorted(failed_ids):
        raise ValueError("Gauntlet failed match ids do not match abnormal retained matches.")
    if sorted(summary.subjectivity_violation_match_ids) != sorted(subjectivity_ids):
        raise ValueError("Gauntlet subjectivity match ids do not match retained matches.")
    if set(row.match_id for row in summary.failure_rows) != set(failed_ids):
        raise ValueError("Gauntlet failure rows do not list every abnormal retained match.")
    if dict(summary.command_status_counts) != command_status_counts:
        raise ValueError("Gauntlet command status counts do not match retained matches.")
    if summary.subjectivity_violation_count != subjectivity_violation_count:
        raise ValueError("Gauntlet subjectivity violation count does not match retained matches.")
    if dict(summary.status_counts) != _count_match_field(matches, "status"):
        raise ValueError("Gauntlet status counts do not match retained matches.")
    if dict(summary.outcome_counts) != _count_match_field(matches, "outcome"):
        raise ValueError("Gauntlet outcome counts do not match retained matches.")

    _validate_gauntlet_performance(summary, matches)
    _validate_gauntlet_gate(summary, failed_ids, subjectivity_ids, command_status_counts)
    _validate_gauntlet_latency(summary, len(matches))
    _validate_gauntlet_event_rows(summary.gauntlet_id, summary.events)
    return summary


def apply_gauntlet_latency_audit(summary: GauntletSummary) -> GauntletSummary:
    """Return a summary with latency audit fields computed from retained rows."""
    latency_status, latency_reasons, latency_thresholds = _latency_audit(summary.performance, len(summary.matches))
    return summary.model_copy(
        update={
            "latency_status": latency_status,
            "latency_reasons": latency_reasons,
            "latency_thresholds": latency_thresholds,
        }
    )


def project_watcher_state(summary: GauntletSummary, events: Optional[list[GauntletEvent]] = None) -> GauntletWatcherState:
    """Project summary and optional live events into the watcher view model."""
    summary = apply_gauntlet_latency_audit(summary)
    validate_gauntlet_summary_evidence(summary)
    event_rows = events if events is not None else summary.events
    _validate_gauntlet_event_rows(summary.gauntlet_id, event_rows)
    active = next((event for event in reversed(event_rows) if event.event_type == "MATCH_STARTED"), None)
    terminal_types = {"MATCH_COMPLETED", "MATCH_FAILED", "GAUNTLET_COMPLETED"}
    if active and any(event.cursor > active.cursor and event.event_type in terminal_types for event in event_rows):
        active = None
    latest_match = summary.matches[-1] if summary.matches else None
    latest_failure = next((event.message or event.status for event in reversed(event_rows) if event.event_type == "MATCH_FAILED"), None)
    status = "completed" if any(event.event_type == "GAUNTLET_COMPLETED" for event in event_rows) else "running" if active else "summary"
    return GauntletWatcherState(
        gauntlet_id=summary.gauntlet_id,
        mode=summary.mode,
        status=status,
        active_match_id=active.match_id if active else None,
        active_match_index=active.match_index if active else None,
        completed_count=summary.completed_count,
        failed_count=summary.failed_count,
        pending_count=summary.pending_count,
        latest_outcome=_get_value(latest_match, "outcome") if latest_match else None,
        latest_failure=latest_failure,
        ratings=dict(summary.ratings),
        rating_series=list(summary.rating_series),
        status_counts=dict(summary.status_counts),
        outcome_counts=dict(summary.outcome_counts),
        command_status_counts=dict(summary.command_status_counts),
        performance=summary.performance,
        artifact_paths=list(summary.artifact_paths),
        failure_rows=list(summary.failure_rows),
        subjectivity_status=summary.subjectivity_status,
        subjectivity_violation_count=summary.subjectivity_violation_count,
        gate_status=summary.gate_status,
        gate_reasons=list(summary.gate_reasons),
        latency_status=summary.latency_status,
        latency_reasons=list(summary.latency_reasons),
        latency_thresholds=dict(summary.latency_thresholds),
        subjectivity_violation_match_ids=list(summary.subjectivity_violation_match_ids),
        recent_events=list(event_rows[-20:]),
    )


def project_live_watcher_state(gauntlet_id: str, events: list[GauntletEvent]) -> GauntletWatcherState:
    """Project live watcher events before retained summary JSON exists."""
    if not events:
        raise ValueError("Live watcher state requires at least one gauntlet event.")
    _validate_gauntlet_event_rows(gauntlet_id, events)
    started = next((event for event in events if event.event_type == "GAUNTLET_STARTED"), None)
    mode = _live_mode(started)
    scheduled_count = _live_scheduled_count(started)
    completed = _events_by_match(events, "MATCH_COMPLETED")
    failed = _events_by_match(events, "MATCH_FAILED")
    progress = _events_by_match(events, "MATCH_PROGRESS")
    completed_count = len(completed)
    failed_count = len(failed)
    pending_count = max(0, scheduled_count - completed_count - failed_count) if scheduled_count is not None else 0
    active = _live_active_match(events)
    latest_progress = next((event for event in reversed(events) if event.event_type == "MATCH_PROGRESS"), None)
    latest_failure = next((event.message or event.status for event in reversed(events) if event.event_type == "MATCH_FAILED"), None)
    command_status_counts = _sum_live_command_status_counts(progress.values())
    subjectivity_violation_count = _sum_live_int(progress.values(), "subjectivity_violation_count")
    subjectivity_status: Literal["not_run", "passed", "failed"] = (
        "failed"
        if subjectivity_violation_count > 0 or any(event.payload.get("subjectivity_status") == "failed" for event in progress.values())
        else "passed" if progress else "not_run"
    )
    gate_reasons = _live_gate_reasons(
        pending_count=pending_count,
        failed_count=failed_count,
        subjectivity_violation_count=subjectivity_violation_count,
        command_status_counts=command_status_counts,
    )
    gate_status = _live_gate_status(
        has_progress=bool(progress),
        pending_count=pending_count,
        gate_reasons=gate_reasons,
    )
    performance = _live_performance_summary(progress.values())
    latency_status, latency_reasons, latency_thresholds = _latency_audit(
        performance,
        len(progress),
    )
    return GauntletWatcherState(
        gauntlet_id=gauntlet_id,
        mode=mode,
        status="completed" if any(event.event_type == "GAUNTLET_COMPLETED" for event in events) else "running",
        active_match_id=active.match_id if active else None,
        active_match_index=active.match_index if active else None,
        completed_count=completed_count,
        failed_count=failed_count,
        pending_count=pending_count,
        latest_outcome=_optional_live_str(latest_progress, "outcome"),
        latest_failure=latest_failure,
        ratings=_live_ratings(events),
        rating_series=_live_rating_series(events),
        status_counts=_count_event_statuses([*completed.values(), *failed.values()]),
        outcome_counts=_count_live_payload_field(progress.values(), "outcome"),
        command_status_counts=command_status_counts,
        performance=performance,
        artifact_paths=_live_artifact_paths(progress.values()),
        failure_rows=_live_failure_rows(failed.values(), progress),
        subjectivity_status=subjectivity_status,
        subjectivity_violation_count=subjectivity_violation_count,
        gate_status=gate_status,
        gate_reasons=gate_reasons,
        latency_status=latency_status,
        latency_reasons=latency_reasons,
        latency_thresholds=latency_thresholds,
        subjectivity_violation_match_ids=[
            match_id
            for match_id, event in sorted(progress.items())
            if _live_has_subjectivity_violation(event)
        ],
        recent_events=list(events[-20:]),
    )


def _live_mode(started: Optional[GauntletEvent]) -> GauntletMode:
    raw = started.payload.get("mode") if started else None
    if raw in {"smoke", "rotation", "content", "regression", "release"}:
        return cast(GauntletMode, raw)
    return "smoke"


def _live_scheduled_count(started: Optional[GauntletEvent]) -> Optional[int]:
    raw = started.payload.get("scheduled_count") if started else None
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        return None
    return max(0, int(raw))


def _events_by_match(
    events: list[GauntletEvent],
    event_type: GauntletEventType,
) -> dict[str, GauntletEvent]:
    rows: dict[str, GauntletEvent] = {}
    for event in events:
        if event.event_type == event_type and event.match_id is not None:
            rows[event.match_id] = event
    return dict(sorted(rows.items()))


def _live_active_match(events: list[GauntletEvent]) -> Optional[GauntletEvent]:
    terminal_by_match = {
        event.match_id: event.cursor
        for event in events
        if event.match_id is not None and event.event_type in {"MATCH_COMPLETED", "MATCH_FAILED"}
    }
    for event in reversed(events):
        if event.event_type != "MATCH_STARTED" or event.match_id is None:
            continue
        if terminal_by_match.get(event.match_id, 0) > event.cursor:
            continue
        if any(row.event_type == "GAUNTLET_COMPLETED" and row.cursor > event.cursor for row in events):
            return None
        return event
    return None


def _sum_live_command_status_counts(events: Iterable[GauntletEvent]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for event in events:
        raw = event.payload.get("command_status_counts")
        if not isinstance(raw, dict):
            continue
        for status, count in raw.items():
            if isinstance(count, bool) or not isinstance(count, (int, float)):
                continue
            key = str(status)
            counts[key] = counts.get(key, 0) + int(count)
    return dict(sorted(counts.items()))


def _sum_live_int(events: Iterable[GauntletEvent], key: str) -> int:
    total = 0
    for event in events:
        raw = event.payload.get(key)
        if isinstance(raw, bool) or not isinstance(raw, (int, float)):
            continue
        total += int(raw)
    return total


def _live_has_subjectivity_violation(event: GauntletEvent) -> bool:
    count = _live_number(event, "subjectivity_violation_count")
    return (count is not None and count > 0) or event.payload.get("subjectivity_status") == "failed"


def _live_gate_reasons(
    *,
    pending_count: int,
    failed_count: int,
    subjectivity_violation_count: int,
    command_status_counts: dict[str, int],
) -> list[str]:
    reasons: list[str] = []
    if pending_count:
        reasons.append("pending_matches")
    if failed_count:
        reasons.append("failed_matches")
    if subjectivity_violation_count:
        reasons.append("subjectivity_violations")
    for status in ("stale", "error", "missing_result"):
        if command_status_counts.get(status, 0) > 0:
            reasons.append(f"{status}_commands")
    return reasons


def _live_gate_status(
    *,
    has_progress: bool,
    pending_count: int,
    gate_reasons: list[str],
) -> GauntletGateStatus:
    if not has_progress:
        return "running" if pending_count else "not_run"
    if gate_reasons:
        has_only_pending = pending_count > 0 and not any(reason != "pending_matches" for reason in gate_reasons)
        return "running" if has_only_pending else "failed"
    return "passed"


def _live_performance_summary(events: Iterable[GauntletEvent]) -> Optional[GauntletPerformanceSummary]:
    rows = list(events)
    if not rows:
        return None
    command_counts = [_live_number(event, "command_count") for event in rows]
    elapsed_values = [_live_number(event, "elapsed_ms") for event in rows]
    command_counts_int = [int(value) for value in command_counts if value is not None]
    elapsed = [value for value in elapsed_values if value is not None]
    command_total = [_live_number(event, "max_command_total_ms") for event in rows]
    server_command = [_live_number(event, "max_server_command_ms") for event in rows]
    local_decision = [_live_number(event, "max_local_decision_ms") for event in rows]
    command_total_values = [value for value in command_total if value is not None]
    server_command_values = [value for value in server_command if value is not None]
    local_decision_values = [value for value in local_decision if value is not None]
    stages = _live_stage_summary(rows, "stage_samples_ms")
    normal_stages = _live_stage_summary(rows, "normal_stage_samples_ms")
    diagnostic_stages = _live_stage_summary(rows, "diagnostic_stage_samples_ms")
    return GauntletPerformanceSummary(
        match_count=len(rows),
        total_command_count=sum(command_counts_int),
        average_command_count=round(sum(command_counts_int) / len(command_counts_int), 3) if command_counts_int else None,
        total_elapsed_ms=round(sum(elapsed), 3) if elapsed else 0.0,
        average_elapsed_ms=round(sum(elapsed) / len(elapsed), 3) if elapsed else None,
        max_elapsed_ms=round(max(elapsed), 3) if elapsed else None,
        max_command_total_ms=round(max(command_total_values), 3) if command_total_values else None,
        max_server_command_ms=round(max(server_command_values), 3) if server_command_values else None,
        max_local_decision_ms=round(max(local_decision_values), 3) if local_decision_values else None,
        stages=stages,
        normal_stages=normal_stages,
        diagnostic_stages=diagnostic_stages,
    )


def _live_number(event: GauntletEvent, key: str) -> Optional[float]:
    raw = event.payload.get(key)
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        return None
    return float(raw)


def _live_stage_summary(events: list[GauntletEvent], key: str) -> dict[str, GauntletLatencyStageSummary]:
    samples: dict[str, list[float]] = {}
    for event in events:
        raw = event.payload.get(key)
        if not isinstance(raw, dict):
            continue
        for stage_name, values in raw.items():
            if not isinstance(values, list):
                continue
            for value in values:
                if isinstance(value, bool) or not isinstance(value, (int, float)):
                    continue
                samples.setdefault(str(stage_name), []).append(float(value))
    return {
        stage_name: _stage_summary(values)
        for stage_name, values in sorted(samples.items())
        if values
    }


def _stage_summary(values: list[float]) -> GauntletLatencyStageSummary:
    ordered = sorted(values)
    return GauntletLatencyStageSummary(
        sample_count=len(ordered),
        mean_ms=round(sum(ordered) / len(ordered), 3),
        p95_ms=_percentile_stage_ms(ordered, 0.95),
        p99_ms=_percentile_stage_ms(ordered, 0.99),
        max_ms=round(max(ordered), 3),
    )


def _percentile_stage_ms(values: list[float], percentile: float) -> Optional[float]:
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, math.ceil(percentile * len(ordered)) - 1)
    return round(ordered[index], 3)


def _optional_live_str(event: Optional[GauntletEvent], key: str) -> Optional[str]:
    if event is None:
        return None
    raw = event.payload.get(key)
    return str(raw) if raw is not None else None


def _live_ratings(events: list[GauntletEvent]) -> dict[str, float]:
    ratings: dict[str, float] = {}
    for event in events:
        if event.event_type != "RATING_UPDATED":
            continue
        raw = event.payload.get("rating_after")
        if not isinstance(raw, dict):
            continue
        for participant, rating in raw.items():
            if isinstance(rating, bool) or not isinstance(rating, (int, float)):
                continue
            ratings[str(participant)] = float(rating)
    return dict(sorted(ratings.items()))


def _live_rating_series(events: list[GauntletEvent]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for event in events:
        if event.event_type != "RATING_UPDATED":
            continue
        raw = event.payload.get("rating_after")
        if not isinstance(raw, dict):
            continue
        for participant, rating in sorted(raw.items()):
            if isinstance(rating, bool) or not isinstance(rating, (int, float)):
                continue
            rows.append({
                "match_index": event.match_index,
                "match_id": event.match_id,
                "participant_id": str(participant),
                "rating": float(rating),
            })
    return rows


def _count_event_statuses(events: Iterable[GauntletEvent]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for event in events:
        key = str(event.status or "unknown")
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items()))


def _count_live_payload_field(events: Iterable[GauntletEvent], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for event in events:
        value = event.payload.get(key)
        bucket = str(value) if value is not None else "unknown"
        counts[bucket] = counts.get(bucket, 0) + 1
    return dict(sorted(counts.items()))


def _live_artifact_paths(events: Iterable[GauntletEvent]) -> list[str]:
    paths: list[str] = []
    for event in events:
        raw = event.payload.get("run_artifact_path")
        if raw is not None:
            paths.append(str(raw))
    return paths


def _live_failure_rows(
    failed_events: Iterable[GauntletEvent],
    progress_by_match: dict[str, GauntletEvent],
) -> list[GauntletFailureRow]:
    rows: list[GauntletFailureRow] = []
    for event in failed_events:
        progress = progress_by_match.get(event.match_id or "")
        rows.append(GauntletFailureRow(
            match_id=event.match_id or "",
            match_index=event.match_index,
            arena_id=_optional_live_str(progress, "arena_id"),
            status=event.status or "failed",
            outcome=_optional_live_str(progress, "outcome"),
            reason=event.message or event.status,
            run_artifact_path=_optional_live_str(progress, "run_artifact_path"),
        ))
    return rows


def _get_value(row: Any, key: str) -> Optional[str]:
    value = _get_raw_value(row, key)
    return str(value) if value is not None else None


def _get_raw_value(row: Any, key: str) -> Any:
    if isinstance(row, dict):
        return row.get(key)
    return getattr(row, key, None)


def _get_int(row: Any, key: str) -> int:
    value = _get_raw_value(row, key)
    return int(value) if value is not None else 0


def _count_match_field(matches: list[Any], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for match in matches:
        value = _get_raw_value(match, key)
        bucket = str(value) if value is not None else "unknown"
        counts[bucket] = counts.get(bucket, 0) + 1
    return dict(sorted(counts.items()))


def _sum_command_status_counts(matches: list[Any]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for match in matches:
        row = _get_raw_value(match, "command_status_counts")
        if not isinstance(row, dict):
            continue
        for status, count in row.items():
            key = str(status)
            counts[key] = counts.get(key, 0) + int(count)
    return dict(sorted(counts.items()))


def _match_has_subjectivity_violation(match: Any) -> bool:
    status = str(_get_raw_value(match, "status") or "").lower()
    return (
        "subjectivity" in status
        or "leak" in status
        or _get_raw_value(match, "subjectivity_status") == "failed"
        or _get_int(match, "subjectivity_violation_count") > 0
    )


def _gauntlet_abnormal_reason(match: Any) -> Optional[str]:
    status = str(_get_raw_value(match, "status") or "")
    if status not in {"encounter_ended", "ENDED", "completed"}:
        return status
    if _match_has_subjectivity_violation(match):
        return "subjectivity_violation"
    command_statuses = _get_raw_value(match, "command_status_counts")
    if isinstance(command_statuses, dict):
        for command_status in ("stale", "error", "missing_result"):
            if int(command_statuses.get(command_status, 0)) > 0:
                return f"{command_status}_command"
    return None


def _validate_gauntlet_performance(summary: GauntletSummary, matches: list[Any]) -> None:
    if not matches:
        if summary.performance is not None:
            raise ValueError("Gauntlet performance summary exists without retained matches.")
        return
    if summary.performance is None:
        raise ValueError("Gauntlet performance summary is missing retained matches.")
    command_total = sum(_get_int(match, "command_count") for match in matches)
    if summary.performance.match_count != len(matches):
        raise ValueError("Gauntlet performance match count does not match retained matches.")
    if summary.performance.total_command_count != command_total:
        raise ValueError("Gauntlet performance command count does not match retained matches.")
    expected_samples = {
        "command_total_sample_count": len(_latency_samples(matches, "command_total_samples_ms")),
        "server_command_sample_count": len(_latency_samples(matches, "server_command_samples_ms")),
        "local_decision_sample_count": len(_latency_samples(matches, "local_decision_samples_ms")),
        "normal_command_total_sample_count": len(_latency_samples(matches, "normal_command_total_samples_ms")),
        "normal_server_command_sample_count": len(_latency_samples(matches, "normal_server_command_samples_ms")),
        "normal_local_decision_sample_count": len(_latency_samples(matches, "normal_local_decision_samples_ms")),
        "diagnostic_command_total_sample_count": len(_latency_samples(matches, "diagnostic_command_total_samples_ms")),
        "diagnostic_server_command_sample_count": len(_latency_samples(matches, "diagnostic_server_command_samples_ms")),
        "diagnostic_local_decision_sample_count": len(_latency_samples(matches, "diagnostic_local_decision_samples_ms")),
    }
    for field_name, expected_count in expected_samples.items():
        if getattr(summary.performance, field_name) != expected_count:
            raise ValueError("Gauntlet performance latency sample counts do not match retained matches.")
    expected_stage_counts = {
        "stages": _stage_sample_counts(matches, "stage_samples_ms"),
        "normal_stages": _stage_sample_counts(matches, "normal_stage_samples_ms"),
        "diagnostic_stages": _stage_sample_counts(matches, "diagnostic_stage_samples_ms"),
    }
    for field_name, expected_counts in expected_stage_counts.items():
        actual_counts = {
            stage_name: stage.sample_count
            for stage_name, stage in getattr(summary.performance, field_name).items()
        }
        if actual_counts != expected_counts:
            raise ValueError("Gauntlet performance stage sample counts do not match retained matches.")


def _validate_gauntlet_gate(
    summary: GauntletSummary,
    failed_ids: list[str],
    subjectivity_ids: list[str],
    command_status_counts: dict[str, int],
) -> None:
    expected_reasons: list[str] = []
    if summary.pending_count:
        expected_reasons.append("pending_matches")
    if failed_ids:
        expected_reasons.append("failed_matches")
    if subjectivity_ids:
        expected_reasons.append("subjectivity_violations")
    for status in ("stale", "error", "missing_result"):
        if command_status_counts.get(status, 0) > 0:
            expected_reasons.append(f"{status}_commands")
    if summary.gate_reasons != expected_reasons:
        raise ValueError("Gauntlet gate reasons do not match retained evidence.")

    if not summary.matches:
        expected_status: GauntletGateStatus = "not_run"
    elif expected_reasons:
        has_only_pending = summary.pending_count > 0 and not any(reason != "pending_matches" for reason in expected_reasons)
        expected_status = "running" if has_only_pending else "failed"
    else:
        expected_status = "passed"
    if summary.gate_status != expected_status:
        raise ValueError("Gauntlet gate status does not match retained evidence.")


def _validate_gauntlet_latency(summary: GauntletSummary, match_count: int) -> None:
    expected_status, expected_reasons, expected_thresholds = _latency_audit(summary.performance, match_count)
    if summary.latency_status != expected_status:
        raise ValueError("Gauntlet latency status does not match retained timing evidence.")
    if summary.latency_reasons != expected_reasons:
        raise ValueError("Gauntlet latency reasons do not match retained timing evidence.")
    if dict(summary.latency_thresholds) != expected_thresholds:
        raise ValueError("Gauntlet latency thresholds do not match the retained audit contract.")


def _latency_audit(
    performance: Optional[GauntletPerformanceSummary],
    match_count: int,
) -> tuple[GauntletLatencyStatus, list[str], dict[str, float]]:
    thresholds = {
        "command_total_p95_ms": GAUNTLET_COMMAND_TOTAL_P95_TARGET_MS,
        "command_total_p99_ms": GAUNTLET_COMMAND_TOTAL_P99_TARGET_MS,
        "local_decision_p99_ms": GAUNTLET_LOCAL_DECISION_P99_TARGET_MS,
        "legacy_max_command_total_ms": GAUNTLET_LEGACY_MAX_COMMAND_TOTAL_TARGET_MS,
        "legacy_max_local_decision_ms": GAUNTLET_LEGACY_MAX_LOCAL_DECISION_TARGET_MS,
    }
    if match_count == 0:
        return "not_run", [], thresholds
    if performance is None:
        return "failed", ["missing_performance_summary"], thresholds

    reasons: list[str] = []
    command_total_p95 = _audit_latency_value(
        performance.normal_command_total_sample_count,
        performance.normal_command_total_p95_ms,
        performance.command_total_p95_ms,
    )
    command_total_p99 = _audit_latency_value(
        performance.normal_command_total_sample_count,
        performance.normal_command_total_p99_ms,
        performance.command_total_p99_ms,
    )
    local_decision_p99 = _audit_latency_value(
        performance.normal_local_decision_sample_count,
        performance.normal_local_decision_p99_ms,
        performance.local_decision_p99_ms,
    )
    if command_total_p95 is not None or command_total_p99 is not None:
        if command_total_p95 is None:
            reasons.append("missing_command_total_p95_latency")
        elif command_total_p95 > GAUNTLET_COMMAND_TOTAL_P95_TARGET_MS:
            reasons.append("command_total_p95_over_5ms")
        if command_total_p99 is None:
            reasons.append("missing_command_total_p99_latency")
        elif command_total_p99 > GAUNTLET_COMMAND_TOTAL_P99_TARGET_MS:
            reasons.append("command_total_p99_over_10ms")
    elif performance.max_command_total_ms is None:
        reasons.append("missing_command_total_latency")
    elif performance.max_command_total_ms > GAUNTLET_LEGACY_MAX_COMMAND_TOTAL_TARGET_MS:
        reasons.append("command_total_over_10ms")

    if local_decision_p99 is not None:
        if local_decision_p99 > GAUNTLET_LOCAL_DECISION_P99_TARGET_MS:
            reasons.append("local_decision_p99_over_5ms")
    elif performance.max_local_decision_ms is None:
        reasons.append("missing_local_decision_latency")
    elif performance.max_local_decision_ms > GAUNTLET_LEGACY_MAX_LOCAL_DECISION_TARGET_MS:
        reasons.append("local_decision_over_5ms")
    return ("failed" if reasons else "passed"), reasons, thresholds


def _audit_latency_value(normal_sample_count: int, normal_value: Optional[float], fallback_value: Optional[float]) -> Optional[float]:
    if normal_sample_count > 0:
        return normal_value
    return fallback_value


def _latency_samples(matches: list[Any], field_name: str) -> list[float]:
    samples: list[float] = []
    for match in matches:
        raw = _get_raw_value(match, field_name)
        if not isinstance(raw, list):
            continue
        for value in raw:
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                samples.append(float(value))
    return samples


def _stage_sample_counts(matches: list[Any], field_name: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for match in matches:
        raw = _get_raw_value(match, field_name)
        if not isinstance(raw, dict):
            continue
        for stage_name, values in raw.items():
            if not isinstance(values, list):
                continue
            count = sum(1 for value in values if isinstance(value, (int, float)) and not isinstance(value, bool))
            if count:
                key = str(stage_name)
                counts[key] = counts.get(key, 0) + count
    return dict(sorted(counts.items()))


def _validate_gauntlet_event_rows(gauntlet_id: str, events: list[GauntletEvent]) -> None:
    cursors = [event.cursor for event in events]
    if any(cursor <= 0 for cursor in cursors):
        raise ValueError("Gauntlet watcher event cursors must be positive.")
    if cursors != sorted(cursors) or len(cursors) != len(set(cursors)):
        raise ValueError("Gauntlet watcher event cursors must be unique and ordered.")
    if any(event.gauntlet_id != gauntlet_id for event in events):
        raise ValueError("Gauntlet watcher events reference a different gauntlet id.")
