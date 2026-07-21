"""Gauntlet schedules, watcher events, and summaries for AI validation."""

from __future__ import annotations

from collections import deque
from datetime import datetime, timezone
from hashlib import sha256
import math
from pathlib import Path
from typing import Any, Literal, Optional, TypedDict
from uuid import uuid4

from pydantic import BaseModel, Field

from ai.evaluation.artifacts import build_external_selfplay_artifact, write_validation_run_artifact
from ai.evaluation.gauntlet_contract import (
    GauntletEvent,
    GauntletEventIngestRequest,
    GauntletEventSink,
    GauntletEventType,
    GauntletFailureRow,
    GauntletGateStatus,
    GauntletLatencyStatus,
    GauntletLatencyStageSummary,
    GauntletMode,
    GauntletPerformanceSummary,
    GauntletSummary,
    GauntletWatcherState,
    apply_gauntlet_latency_audit,
    project_live_watcher_state,
    project_watcher_state,
    validate_gauntlet_summary_evidence,
)
from ai.evaluation.tournament import EloConfig, RatingSnapshot, TournamentMatchRecord, TournamentSummary, build_tournament_match_record
from ai.external_selfplay import run_external_selfplay
from dnd.scenarios.ai_validation_arenas import list_ai_validation_arena_specs

__all__ = [
    "GauntletEvent",
    "GauntletEventIngestRequest",
    "GauntletEventSink",
    "GauntletEventStream",
    "GauntletEventType",
    "GauntletFailureRow",
    "GauntletGateStatus",
    "GauntletLatencyStatus",
    "GauntletMode",
    "GauntletPerformanceSummary",
    "GauntletSchedule",
    "GauntletScheduleEntry",
    "GauntletSummary",
    "GauntletWatcherState",
    "build_gauntlet_schedule",
    "build_regression_schedule",
    "build_gauntlet_summary",
    "apply_gauntlet_latency_audit",
    "project_live_watcher_state",
    "project_watcher_state",
    "run_ai_gauntlet",
    "validate_gauntlet_summary_evidence",
    "write_gauntlet_summary",
]


class _RotationProfile(TypedDict):
    """Internal six-slot rotation profile."""

    hero_profile: str
    monster_profile: str
    tags: tuple[str, ...]


class GauntletScheduleEntry(BaseModel):
    """One deterministic match request in a gauntlet schedule."""

    match_index: int = Field(description="Zero-based schedule index.")
    arena_id: str = Field(description="Validation arena id.")
    random_seed: int = Field(description="Deterministic random seed.")
    hero_first: bool = Field(description="Whether the hero side opens the match.")
    controller_profile: str = Field(default="unified_ai", description="Controller policy/profile id.")
    hero_profile: Optional[str] = Field(default=None, description="Hero class/loadout profile.")
    monster_profile: Optional[str] = Field(default=None, description="Monster roster/loadout profile.")
    policy_version: Optional[str] = Field(default=None, description="Policy version or hash under test.")
    tags: tuple[str, ...] = Field(default_factory=tuple, description="Schedule tags used by dashboards.")


class GauntletSchedule(BaseModel):
    """Named repeatable gauntlet schedule."""

    schema_version: Literal[1] = Field(default=1, description="Gauntlet schedule schema version.")
    gauntlet_id: str = Field(description="Stable gauntlet batch id.")
    mode: GauntletMode = Field(description="Gauntlet mode.")
    created_at: str = Field(description="UTC timestamp when the schedule was created.")
    entries: list[GauntletScheduleEntry] = Field(default_factory=list, description="Scheduled matches.")
    schedule_hash: str = Field(description="Stable hash of scheduled match inputs.")


class GauntletEventStream:
    """Small in-memory bounded event history for live gauntlet watchers."""

    def __init__(self, *, max_events: int = 512) -> None:
        self._max_events = max_events
        self._events: deque[GauntletEvent] = deque(maxlen=max_events)
        self._cursor = 0

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
        """Append and return one watcher event."""
        self._cursor += 1
        event = GauntletEvent(
            cursor=self._cursor,
            event_type=event_type,
            gauntlet_id=gauntlet_id,
            match_id=match_id,
            match_index=match_index,
            status=status,
            message=message,
            payload=payload or {},
            created_at=_utc_now(),
        )
        self._events.append(event)
        return event

    def since(self, cursor: int = 0) -> list[GauntletEvent]:
        """Return retained events with cursor greater than `cursor`."""
        return [event for event in self._events if event.cursor > cursor]


def build_gauntlet_schedule(
    mode: GauntletMode,
    *,
    arena_ids: Optional[list[str]] = None,
    seeds: Optional[list[int]] = None,
    policy_version: Optional[str] = None,
) -> GauntletSchedule:
    """Build a named repeatable gauntlet schedule."""
    selected_arenas = arena_ids or _default_arenas_for_mode(mode)
    _validate_arena_ids(selected_arenas)
    selected_seeds = seeds or _default_seeds_for_mode(mode)
    entries: list[GauntletScheduleEntry] = []
    rotation_profiles = _rotation_profiles()
    index = 0
    for arena_id in selected_arenas:
        for seed_offset, seed in enumerate(selected_seeds):
            profile = rotation_profiles[index % len(rotation_profiles)]
            entries.append(
                GauntletScheduleEntry(
                    match_index=index,
                    arena_id=arena_id,
                    random_seed=seed,
                    hero_first=seed_offset % 2 == 0,
                    controller_profile="unified_ai",
                    hero_profile=profile["hero_profile"],
                    monster_profile=profile["monster_profile"],
                    policy_version=policy_version,
                    tags=tuple(profile["tags"]) + (mode,),
                )
            )
            index += 1
    gauntlet_id = _new_gauntlet_id(mode)
    return GauntletSchedule(
        gauntlet_id=gauntlet_id,
        mode=mode,
        created_at=_utc_now(),
        entries=entries,
        schedule_hash=_schedule_hash(entries),
    )


def build_regression_schedule(
    summary: GauntletSummary,
    *,
    policy_version: Optional[str] = None,
) -> GauntletSchedule:
    """Build a replay schedule from retained failed/abnormal summary rows."""
    original_entries = {
        int(_get_value(entry, "match_index")): entry
        for entry in summary.schedule
        if _get_value(entry, "match_index") is not None
    }
    entries: list[GauntletScheduleEntry] = []
    for failure in summary.failure_rows:
        if failure.match_index is None:
            continue
        source_entry = original_entries.get(failure.match_index)
        if source_entry is None:
            continue
        original_tags = _get_tags(source_entry)
        status_tag = f"status:{failure.status}"
        tags = tuple(dict.fromkeys(original_tags + ("regression", "replay", status_tag)))
        entries.append(
            GauntletScheduleEntry(
                match_index=len(entries),
                arena_id=str(_require_value(source_entry, "arena_id")),
                random_seed=int(_require_value(source_entry, "random_seed")),
                hero_first=bool(_require_value(source_entry, "hero_first")),
                controller_profile=str(_get_value(source_entry, "controller_profile") or "unified_ai"),
                hero_profile=_optional_str(_get_value(source_entry, "hero_profile")),
                monster_profile=_optional_str(_get_value(source_entry, "monster_profile")),
                policy_version=policy_version if policy_version is not None else _optional_str(_get_value(source_entry, "policy_version")),
                tags=tags,
            )
        )
    _validate_arena_ids([entry.arena_id for entry in entries])
    return GauntletSchedule(
        gauntlet_id=_new_gauntlet_id("regression"),
        mode="regression",
        created_at=_utc_now(),
        entries=entries,
        schedule_hash=_schedule_hash(entries),
    )


def run_ai_gauntlet(
    schedule: GauntletSchedule,
    *,
    max_commands: int = 80,
    elo_config: Optional[EloConfig] = None,
    runs_output_directory: Optional[Path | str] = None,
    gauntlet_output_directory: Optional[Path | str] = "ai/evidence/gauntlets",
    event_stream: Optional[GauntletEventSink] = None,
) -> GauntletSummary:
    """Run exactly the rows in a gauntlet schedule."""
    stream = event_stream or GauntletEventStream()
    stream.append(
        event_type="GAUNTLET_STARTED",
        gauntlet_id=schedule.gauntlet_id,
        status="running",
        payload={"mode": schedule.mode, "scheduled_count": len(schedule.entries)},
    )
    config = elo_config or EloConfig()
    tournament = TournamentSummary(
        tournament_id=schedule.gauntlet_id,
        generated_at=_utc_now(),
        elo_config=config,
        arena_ids=list(dict.fromkeys(entry.arena_id for entry in schedule.entries)),
    )
    ratings: dict[str, float] = {}
    for entry in schedule.entries:
        match_id = f"{schedule.gauntlet_id}-{entry.match_index:04d}"
        stream.append(
            event_type="MATCH_STARTED",
            gauntlet_id=schedule.gauntlet_id,
            match_id=match_id,
            match_index=entry.match_index,
            status="running",
            payload={"arena_id": entry.arena_id, "seed": entry.random_seed},
        )
        result = run_external_selfplay(
            entry.arena_id,
            max_commands=max_commands,
            hero_first=entry.hero_first,
            random_seed=entry.random_seed,
        )
        run_artifact_path: Optional[str] = None
        if runs_output_directory is not None:
            artifact = build_external_selfplay_artifact(
                result,
                run_id=f"{match_id}-{entry.arena_id}",
                random_seed=entry.random_seed,
            )
            run_artifact_path = str(write_validation_run_artifact(artifact, runs_output_directory))
        record = build_tournament_match_record(
            result,
            match_id=match_id,
            random_seed=entry.random_seed,
            hero_first=entry.hero_first,
            ratings=ratings,
            elo_config=config,
            run_artifact_path=run_artifact_path,
        )
        tournament.matches.append(record)
        stream.append(
            event_type="MATCH_PROGRESS",
            gauntlet_id=schedule.gauntlet_id,
            match_id=record.match_id,
            match_index=entry.match_index,
            status=record.status,
            payload={
                "arena_id": record.arena_id,
                "outcome": record.outcome,
                "command_count": record.command_count,
                "elapsed_ms": record.elapsed_ms,
                "command_status_counts": record.command_status_counts,
                "subjectivity_status": record.subjectivity_status,
                "subjectivity_violation_count": record.subjectivity_violation_count,
                "max_command_total_ms": record.max_command_total_ms,
                "max_server_command_ms": record.max_server_command_ms,
                "max_local_decision_ms": record.max_local_decision_ms,
                "command_total_p95_ms": record.command_total_p95_ms,
                "command_total_p99_ms": record.command_total_p99_ms,
                "server_command_p95_ms": record.server_command_p95_ms,
                "server_command_p99_ms": record.server_command_p99_ms,
                "local_decision_p95_ms": record.local_decision_p95_ms,
                "local_decision_p99_ms": record.local_decision_p99_ms,
                "normal_command_total_p95_ms": record.normal_command_total_p95_ms,
                "normal_command_total_p99_ms": record.normal_command_total_p99_ms,
                "normal_server_command_p95_ms": record.normal_server_command_p95_ms,
                "normal_server_command_p99_ms": record.normal_server_command_p99_ms,
                "normal_local_decision_p95_ms": record.normal_local_decision_p95_ms,
                "normal_local_decision_p99_ms": record.normal_local_decision_p99_ms,
                "diagnostic_command_total_p95_ms": record.diagnostic_command_total_p95_ms,
                "diagnostic_command_total_p99_ms": record.diagnostic_command_total_p99_ms,
                "diagnostic_server_command_p95_ms": record.diagnostic_server_command_p95_ms,
                "diagnostic_server_command_p99_ms": record.diagnostic_server_command_p99_ms,
                "diagnostic_local_decision_p95_ms": record.diagnostic_local_decision_p95_ms,
                "diagnostic_local_decision_p99_ms": record.diagnostic_local_decision_p99_ms,
                "stage_samples_ms": record.stage_samples_ms,
                "normal_stage_samples_ms": record.normal_stage_samples_ms,
                "diagnostic_stage_samples_ms": record.diagnostic_stage_samples_ms,
                "run_artifact_path": record.run_artifact_path,
            },
        )
        ratings.update(record.rating_after)
        for participant_id, rating in sorted(ratings.items()):
            tournament.rating_series.append(
                RatingSnapshot(
                    match_index=entry.match_index,
                    match_id=record.match_id,
                    participant_id=participant_id,
                    rating=round(rating, 3),
                )
            )
        stream.append(
            event_type="RATING_UPDATED",
            gauntlet_id=schedule.gauntlet_id,
            match_id=record.match_id,
            match_index=entry.match_index,
            status="ratings_updated",
            payload={
                "rating_after": dict(record.rating_after),
                "rating_delta": dict(record.rating_delta),
            },
        )
        event_type: GauntletEventType = "MATCH_COMPLETED" if _is_normal_match(record) else "MATCH_FAILED"
        stream.append(
            event_type=event_type,
            gauntlet_id=schedule.gauntlet_id,
            match_id=record.match_id,
            match_index=entry.match_index,
            status=record.status,
            message=_abnormal_reason(record),
            payload={
                "outcome": record.outcome,
                "command_count": record.command_count,
                "command_status_counts": record.command_status_counts,
                "subjectivity_status": record.subjectivity_status,
                "subjectivity_violation_count": record.subjectivity_violation_count,
            },
        )
    tournament.ratings = {participant_id: round(rating, 3) for participant_id, rating in sorted(ratings.items())}
    summary = build_gauntlet_summary(schedule, tournament, stream.since(0))
    stream.append(event_type="SUMMARY_WRITTEN", gauntlet_id=schedule.gauntlet_id, status="summary_ready")
    stream.append(event_type="GAUNTLET_COMPLETED", gauntlet_id=schedule.gauntlet_id, status="completed")
    summary = summary.model_copy(update={"events": stream.since(0)})
    if gauntlet_output_directory is not None:
        write_gauntlet_summary(summary, gauntlet_output_directory)
    return summary


def build_gauntlet_summary(
    schedule: GauntletSchedule,
    tournament: TournamentSummary,
    events: Optional[list[GauntletEvent]] = None,
) -> GauntletSummary:
    """Build a watcher-ready gauntlet summary from tournament records."""
    failed_ids = [record.match_id for record in tournament.matches if not _is_normal_match(record)]
    completed_count = len(tournament.matches) - len(failed_ids)
    pending_count = max(0, len(schedule.entries) - len(tournament.matches))
    subjectivity_violations = _subjectivity_violations(tournament.matches)
    command_status_counts = _command_status_counts(tournament.matches)
    gate_reasons = _gate_reasons(
        failed_count=len(failed_ids),
        pending_count=pending_count,
        subjectivity_violations=subjectivity_violations,
        command_status_counts=command_status_counts,
    )
    summary = GauntletSummary(
        gauntlet_id=schedule.gauntlet_id,
        mode=schedule.mode,
        generated_at=tournament.generated_at,
        schedule_hash=schedule.schedule_hash,
        schedule=list(schedule.entries),
        matches=list(tournament.matches),
        ratings=dict(tournament.ratings),
        rating_series=list(tournament.rating_series),
        events=events or [],
        status_counts=_counts_by_field(tournament.matches, "status"),
        outcome_counts=_counts_by_field(tournament.matches, "outcome"),
        command_status_counts=command_status_counts,
        performance=_performance_summary(tournament.matches),
        artifact_paths=_artifact_paths(tournament.matches),
        failure_rows=_failure_rows(tournament.matches, schedule),
        subjectivity_status="failed" if subjectivity_violations else "passed" if tournament.matches else "not_run",
        subjectivity_violation_count=sum(_get_int(record, "subjectivity_violation_count") for record in tournament.matches),
        gate_status=_gate_status(match_count=len(tournament.matches), gate_reasons=gate_reasons, pending_count=pending_count),
        gate_reasons=gate_reasons,
        completed_count=completed_count,
        failed_count=len(failed_ids),
        pending_count=pending_count,
        failed_match_ids=failed_ids,
        subjectivity_violation_match_ids=subjectivity_violations,
    )
    return apply_gauntlet_latency_audit(summary)


def write_gauntlet_summary(summary: GauntletSummary, output_directory: Path | str) -> Path:
    """Persist gauntlet summary JSON and update a `latest.json` pointer."""
    summary = apply_gauntlet_latency_audit(summary)
    validate_gauntlet_summary_evidence(summary)
    directory = Path(output_directory)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{summary.gauntlet_id}.json"
    with path.open("x", encoding="utf-8") as handle:
        handle.write(summary.model_dump_json(indent=2))
        handle.write("\n")
    latest = directory / "latest.json"
    latest.write_text(summary.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return path


def _default_arenas_for_mode(mode: GauntletMode) -> list[str]:
    if mode == "smoke":
        return ["standard_skeleton_doors"]
    if mode == "rotation":
        return ["standard_skeleton_doors"]
    if mode == "content":
        return ["srd_low_cr_patrol", "srd_undead_crypt", "srd_goblinoid_warband"]
    if mode == "release":
        return ["standard_skeleton_doors", "caster_crossfire", "srd_low_cr_patrol", "srd_undead_crypt"]
    return ["standard_skeleton_doors"]


def _default_seeds_for_mode(mode: GauntletMode) -> list[int]:
    if mode == "smoke":
        return [1]
    if mode == "rotation":
        return [1, 2, 3, 4, 5, 6]
    if mode == "release":
        return [1, 2, 3]
    return [1, 2]


def _validate_arena_ids(arena_ids: list[str]) -> None:
    valid = {spec.arena_id for spec in list_ai_validation_arena_specs()}
    missing = sorted(set(arena_ids) - valid)
    if missing:
        raise ValueError(
            "Unknown gauntlet arena ids: "
            + ", ".join(missing)
            + ". Valid arena ids: "
            + ", ".join(sorted(valid))
        )


def _rotation_profiles() -> list[_RotationProfile]:
    return [
        {"hero_profile": "codex_barbarian", "monster_profile": "ai_monsters", "tags": ("codex", "barbarian")},
        {"hero_profile": "codex_sorcerer", "monster_profile": "ai_monsters", "tags": ("codex", "sorcerer")},
        {"hero_profile": "ai_barbarian", "monster_profile": "codex_skeletons", "tags": ("codex", "skeletons", "barbarian")},
        {"hero_profile": "ai_sorcerer", "monster_profile": "codex_skeletons", "tags": ("codex", "skeletons", "sorcerer")},
        {"hero_profile": "ai_barbarian", "monster_profile": "ai_monsters", "tags": ("ai_vs_ai", "barbarian")},
        {"hero_profile": "ai_sorcerer", "monster_profile": "ai_monsters", "tags": ("ai_vs_ai", "sorcerer")},
    ]


def _schedule_hash(entries: list[GauntletScheduleEntry]) -> str:
    payload = "\n".join(entry.model_dump_json() for entry in entries)
    return sha256(payload.encode("utf-8")).hexdigest()[:16]


def _get_value(row: Any, field_name: str) -> Any:
    if isinstance(row, dict):
        return row.get(field_name)
    return getattr(row, field_name, None)


def _require_value(row: Any, field_name: str) -> Any:
    value = _get_value(row, field_name)
    if value is None:
        raise ValueError(f"Regression source schedule entry is missing {field_name}.")
    return value


def _optional_str(value: Any) -> Optional[str]:
    return str(value) if value is not None else None


def _get_tags(row: Any) -> tuple[str, ...]:
    raw = _get_value(row, "tags")
    if raw is None:
        return ()
    if isinstance(raw, str):
        return (raw,)
    return tuple(str(tag) for tag in raw)


def _counts_by_field(records: list[TournamentMatchRecord], field_name: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for record in records:
        value = getattr(record, field_name)
        key = str(value) if value is not None else "unknown"
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items()))


def _performance_summary(records: list[TournamentMatchRecord]) -> Optional[GauntletPerformanceSummary]:
    if not records:
        return None
    command_counts = [record.command_count for record in records]
    elapsed_values = [record.elapsed_ms for record in records]
    command_total_values = [
        value
        for record in records
        if (value := _optional_float(_get_value(record, "max_command_total_ms"))) is not None
    ]
    server_command_values = [
        value
        for record in records
        if (value := _optional_float(_get_value(record, "max_server_command_ms"))) is not None
    ]
    local_decision_values = [
        value
        for record in records
        if (value := _optional_float(_get_value(record, "max_local_decision_ms"))) is not None
    ]
    command_total_samples = _latency_samples(records, "command_total_samples_ms")
    server_command_samples = _latency_samples(records, "server_command_samples_ms")
    local_decision_samples = _latency_samples(records, "local_decision_samples_ms")
    normal_command_total_samples = _latency_samples(records, "normal_command_total_samples_ms")
    normal_server_command_samples = _latency_samples(records, "normal_server_command_samples_ms")
    normal_local_decision_samples = _latency_samples(records, "normal_local_decision_samples_ms")
    diagnostic_command_total_samples = _latency_samples(records, "diagnostic_command_total_samples_ms")
    diagnostic_server_command_samples = _latency_samples(records, "diagnostic_server_command_samples_ms")
    diagnostic_local_decision_samples = _latency_samples(records, "diagnostic_local_decision_samples_ms")
    stage_samples = _stage_latency_samples(records, "stage_samples_ms")
    normal_stage_samples = _stage_latency_samples(records, "normal_stage_samples_ms")
    diagnostic_stage_samples = _stage_latency_samples(records, "diagnostic_stage_samples_ms")
    return GauntletPerformanceSummary(
        match_count=len(records),
        total_command_count=sum(command_counts),
        average_command_count=round(sum(command_counts) / len(command_counts), 3),
        total_elapsed_ms=round(sum(elapsed_values), 3),
        average_elapsed_ms=round(sum(elapsed_values) / len(elapsed_values), 3),
        max_elapsed_ms=round(max(elapsed_values), 3),
        max_command_total_ms=round(max(command_total_values), 3) if command_total_values else None,
        max_server_command_ms=round(max(server_command_values), 3) if server_command_values else None,
        max_local_decision_ms=round(max(local_decision_values), 3) if local_decision_values else None,
        command_total_sample_count=len(command_total_samples),
        server_command_sample_count=len(server_command_samples),
        local_decision_sample_count=len(local_decision_samples),
        normal_command_total_sample_count=len(normal_command_total_samples),
        normal_server_command_sample_count=len(normal_server_command_samples),
        normal_local_decision_sample_count=len(normal_local_decision_samples),
        diagnostic_command_total_sample_count=len(diagnostic_command_total_samples),
        diagnostic_server_command_sample_count=len(diagnostic_server_command_samples),
        diagnostic_local_decision_sample_count=len(diagnostic_local_decision_samples),
        command_total_p95_ms=_percentile_ms(command_total_samples, 0.95),
        command_total_p99_ms=_percentile_ms(command_total_samples, 0.99),
        server_command_p95_ms=_percentile_ms(server_command_samples, 0.95),
        server_command_p99_ms=_percentile_ms(server_command_samples, 0.99),
        local_decision_p95_ms=_percentile_ms(local_decision_samples, 0.95),
        local_decision_p99_ms=_percentile_ms(local_decision_samples, 0.99),
        normal_command_total_p95_ms=_percentile_ms(normal_command_total_samples, 0.95),
        normal_command_total_p99_ms=_percentile_ms(normal_command_total_samples, 0.99),
        normal_server_command_p95_ms=_percentile_ms(normal_server_command_samples, 0.95),
        normal_server_command_p99_ms=_percentile_ms(normal_server_command_samples, 0.99),
        normal_local_decision_p95_ms=_percentile_ms(normal_local_decision_samples, 0.95),
        normal_local_decision_p99_ms=_percentile_ms(normal_local_decision_samples, 0.99),
        diagnostic_command_total_p95_ms=_percentile_ms(diagnostic_command_total_samples, 0.95),
        diagnostic_command_total_p99_ms=_percentile_ms(diagnostic_command_total_samples, 0.99),
        diagnostic_server_command_p95_ms=_percentile_ms(diagnostic_server_command_samples, 0.95),
        diagnostic_server_command_p99_ms=_percentile_ms(diagnostic_server_command_samples, 0.99),
        diagnostic_local_decision_p95_ms=_percentile_ms(diagnostic_local_decision_samples, 0.95),
        diagnostic_local_decision_p99_ms=_percentile_ms(diagnostic_local_decision_samples, 0.99),
        max_normal_command_total_ms=_max_ms(normal_command_total_samples),
        max_normal_server_command_ms=_max_ms(normal_server_command_samples),
        max_normal_local_decision_ms=_max_ms(normal_local_decision_samples),
        max_diagnostic_command_total_ms=_max_ms(diagnostic_command_total_samples),
        max_diagnostic_server_command_ms=_max_ms(diagnostic_server_command_samples),
        max_diagnostic_local_decision_ms=_max_ms(diagnostic_local_decision_samples),
        stages=_stage_latency_summary(stage_samples),
        normal_stages=_stage_latency_summary(normal_stage_samples),
        diagnostic_stages=_stage_latency_summary(diagnostic_stage_samples),
    )


def _artifact_paths(records: list[TournamentMatchRecord]) -> list[str]:
    return [
        record.run_artifact_path
        for record in records
        if record.run_artifact_path is not None
    ]


def _failure_rows(
    records: list[TournamentMatchRecord],
    schedule: GauntletSchedule,
) -> list[GauntletFailureRow]:
    index_by_match_id = {
        f"{schedule.gauntlet_id}-{entry.match_index:04d}": entry.match_index
        for entry in schedule.entries
    }
    return [
        GauntletFailureRow(
            match_id=record.match_id,
            match_index=index_by_match_id.get(record.match_id),
            arena_id=record.arena_id,
            status=record.status,
            outcome=record.outcome,
            reason=_abnormal_reason(record),
            run_artifact_path=record.run_artifact_path,
        )
        for record in records
        if not _is_normal_match(record)
    ]


def _is_normal_match(record: TournamentMatchRecord) -> bool:
    return record.status in {"encounter_ended", "ENDED", "completed"} and _abnormal_reason(record) is None


def _abnormal_reason(record: TournamentMatchRecord) -> Optional[str]:
    if record.status not in {"encounter_ended", "ENDED", "completed"}:
        return record.status
    if _get_value(record, "subjectivity_status") == "failed" or _get_int(record, "subjectivity_violation_count") > 0:
        return "subjectivity_violation"
    command_statuses = _get_value(record, "command_status_counts")
    if isinstance(command_statuses, dict):
        for status in ("stale", "error", "missing_result"):
            if int(command_statuses.get(status, 0)) > 0:
                return f"{status}_command"
    return None


def _subjectivity_violations(records: list[TournamentMatchRecord]) -> list[str]:
    return [
        record.match_id
        for record in records
        if "subjectivity" in record.status.lower()
        or "leak" in record.status.lower()
        or _get_value(record, "subjectivity_status") == "failed"
        or _get_int(record, "subjectivity_violation_count") > 0
    ]


def _command_status_counts(records: list[TournamentMatchRecord]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for record in records:
        row = _get_value(record, "command_status_counts")
        if not isinstance(row, dict):
            continue
        for status, count in row.items():
            key = str(status)
            counts[key] = counts.get(key, 0) + int(count)
    return dict(sorted(counts.items()))


def _gate_reasons(
    *,
    failed_count: int,
    pending_count: int,
    subjectivity_violations: list[str],
    command_status_counts: dict[str, int],
) -> list[str]:
    reasons: list[str] = []
    if pending_count:
        reasons.append("pending_matches")
    if failed_count:
        reasons.append("failed_matches")
    if subjectivity_violations:
        reasons.append("subjectivity_violations")
    for status in ("stale", "error", "missing_result"):
        if command_status_counts.get(status, 0) > 0:
            reasons.append(f"{status}_commands")
    return reasons


def _gate_status(
    *,
    match_count: int,
    gate_reasons: list[str],
    pending_count: int,
) -> GauntletGateStatus:
    if match_count == 0:
        return "not_run"
    if gate_reasons:
        return "running" if pending_count and not any(reason != "pending_matches" for reason in gate_reasons) else "failed"
    return "passed"


def _get_int(row: Any, field_name: str) -> int:
    value = _get_value(row, field_name)
    if value is None:
        return 0
    return int(value)


def _optional_float(value: Any) -> Optional[float]:
    return float(value) if value is not None else None


def _latency_samples(records: list[TournamentMatchRecord], field_name: str) -> list[float]:
    samples: list[float] = []
    for record in records:
        raw = _get_value(record, field_name)
        if not isinstance(raw, list):
            continue
        for value in raw:
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                samples.append(float(value))
    return samples


def _stage_latency_samples(records: list[TournamentMatchRecord], field_name: str) -> dict[str, list[float]]:
    samples: dict[str, list[float]] = {}
    for record in records:
        raw = _get_value(record, field_name)
        if not isinstance(raw, dict):
            continue
        for stage_name, values in raw.items():
            if not isinstance(values, list):
                continue
            for value in values:
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    samples.setdefault(str(stage_name), []).append(float(value))
    return {
        stage_name: values
        for stage_name, values in sorted(samples.items())
        if values
    }


def _stage_latency_summary(stage_samples: dict[str, list[float]]) -> dict[str, GauntletLatencyStageSummary]:
    return {
        stage_name: GauntletLatencyStageSummary(
            sample_count=len(values),
            mean_ms=round(sum(values) / len(values), 3),
            p95_ms=_percentile_ms(values, 0.95),
            p99_ms=_percentile_ms(values, 0.99),
            max_ms=_max_ms(values),
        )
        for stage_name, values in sorted(stage_samples.items())
        if values
    }


def _max_ms(values: list[float]) -> Optional[float]:
    if not values:
        return None
    return round(max(values), 3)


def _percentile_ms(values: list[float], percentile: float) -> Optional[float]:
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, math.ceil(percentile * len(ordered)) - 1)
    return round(ordered[index], 3)


def _new_gauntlet_id(mode: GauntletMode) -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{timestamp}-ai-gauntlet-{mode}-{uuid4().hex[:8]}"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
