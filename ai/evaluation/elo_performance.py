"""Retained-evidence performance analysis for Elo matrix runs."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
import json
import math
from pathlib import Path
from statistics import fmean, median
from typing import Iterable, Optional

from pydantic import BaseModel, Field

from ai.evaluation.elo_contract import EloMatchRecord


CLIENT_STAGE_FIELDS = (
    "pre_command_sync_ms",
    "fact_ms",
    "policy_ms",
    "command_http_ms",
    "command_followup_sync_ms",
)


@dataclass(frozen=True)
class _ArenaPerformanceSample:
    """One raw match row used by the per-arena aggregate."""

    elapsed_ms: float
    command_count: int
    actor_turn_count: int
    final_round: float
    side_order: str


class EloMetricDistribution(BaseModel):
    """Distribution and total for one retained numeric measurement."""

    count: int = Field(description="Number of retained samples.")
    total: float = Field(description="Sum of retained samples.")
    minimum: float = Field(description="Minimum retained sample.")
    mean: float = Field(description="Arithmetic mean.")
    median: float = Field(description="Median sample.")
    p95: float = Field(description="Nearest-rank 95th percentile.")
    p99: float = Field(description="Nearest-rank 99th percentile.")
    maximum: float = Field(description="Maximum retained sample.")


class EloArenaPerformance(BaseModel):
    """Throughput and encounter length for one arena's retained rows."""

    arena_id: str = Field(description="Validation arena id.")
    match_count: int = Field(description="Retained run artifacts included.")
    command_count: int = Field(description="Total commands across included matches.")
    actor_turn_count: int = Field(description="Distinct actor-turns across included matches.")
    side_order_counts: dict[str, int] = Field(description="Included matches by opening-side treatment.")
    match_elapsed_ms: EloMetricDistribution = Field(description="Match wall-clock duration distribution.")
    commands_per_match: float = Field(description="Mean commands per match.")
    actor_turns_per_match: float = Field(description="Mean distinct actor-turns per match.")
    final_round_per_match: float = Field(description="Mean final round number.")
    commands_per_second: float = Field(description="Commands divided by summed match wall time.")
    actor_turns_per_second: float = Field(description="Distinct actor-turns divided by summed match wall time.")


class EloRuntimePerformance(BaseModel):
    """Global, per-arena, and per-stage measurements from raw run artifacts."""

    match_count: int = Field(description="Retained tournament records with match timing.")
    artifact_match_count: int = Field(description="Raw successful run artifacts analyzed.")
    artifact_errors: list[str] = Field(default_factory=list, description="Artifact paths that could not be analyzed.")
    evaluation_wall_elapsed_ms: Optional[float] = Field(
        default=None,
        description="Wall time from schedule creation through final summary generation.",
    )
    evaluator_overhead_ms: Optional[float] = Field(
        default=None,
        description="Wall time outside retained self-play match timers.",
    )
    simulation_time_share_pct: Optional[float] = Field(
        default=None,
        description="Retained self-play match time as a percentage of evaluator wall time.",
    )
    wall_matches_per_minute: Optional[float] = Field(
        default=None,
        description="Completed matches per evaluator wall-clock minute.",
    )
    wall_commands_per_second: Optional[float] = Field(
        default=None,
        description="Commands per evaluator wall-clock second.",
    )
    wall_actor_turns_per_second: Optional[float] = Field(
        default=None,
        description="Actor-turns per evaluator wall-clock second.",
    )
    total_elapsed_ms: float = Field(description="Summed match wall-clock duration.")
    average_elapsed_ms: Optional[float] = Field(default=None, description="Mean match wall-clock duration.")
    p95_elapsed_ms: Optional[float] = Field(default=None, description="95th percentile match duration.")
    max_elapsed_ms: Optional[float] = Field(default=None, description="Maximum match duration.")
    total_command_count: int = Field(description="Total commands across analyzed matches.")
    average_command_count: Optional[float] = Field(default=None, description="Mean commands per match.")
    total_actor_turn_count: int = Field(description="Distinct actor-turns across analyzed matches.")
    average_actor_turn_count: Optional[float] = Field(default=None, description="Mean actor-turns per match.")
    average_final_round: Optional[float] = Field(default=None, description="Mean final encounter round.")
    commands_per_second: Optional[float] = Field(default=None, description="Commands divided by summed match wall time.")
    actor_turns_per_second: Optional[float] = Field(default=None, description="Actor-turns divided by summed match wall time.")
    traced_command_ms: EloMetricDistribution = Field(description="Complete per-command client-loop duration.")
    client_stage_ms: dict[str, EloMetricDistribution] = Field(
        default_factory=dict,
        description="Non-overlapping top-level client-loop stage distributions.",
    )
    client_stage_share_pct: dict[str, float] = Field(
        default_factory=dict,
        description="Stage totals as percentages of complete traced command time.",
    )
    diagnostic_components_ms: dict[str, EloMetricDistribution] = Field(
        default_factory=dict,
        description="Sampled server and engine component distributions.",
    )
    top_server_phases_ms: dict[str, EloMetricDistribution] = Field(
        default_factory=dict,
        description="Highest-total sampled command-server phases.",
    )
    top_engine_phases_ms: dict[str, EloMetricDistribution] = Field(
        default_factory=dict,
        description="Highest-total sampled engine-execution phases.",
    )
    arenas: list[EloArenaPerformance] = Field(
        default_factory=list,
        description="Per-arena throughput and encounter-length rows.",
    )


def analyze_elo_performance(
    records: Iterable[EloMatchRecord],
    *,
    evaluation_started_at: Optional[str] = None,
    evaluation_completed_at: Optional[str] = None,
) -> EloRuntimePerformance:
    """Analyze timing and turn structure directly from retained artifacts.

    Args:
        records: Retained evaluator match records.
        evaluation_started_at: Optional ISO schedule-creation timestamp.
        evaluation_completed_at: Optional ISO final-summary timestamp.

    Returns:
        Typed global, stage, and per-arena performance measurements.
    """
    record_rows = list(records)
    match_elapsed = [
        float(record.base_record.elapsed_ms)
        for record in record_rows
        if record.base_record is not None
    ]
    base_commands = [
        int(record.base_record.command_count)
        for record in record_rows
        if record.base_record is not None
    ]
    client_samples: dict[str, list[float]] = defaultdict(list)
    server_phase_samples: dict[str, list[float]] = defaultdict(list)
    engine_phase_samples: dict[str, list[float]] = defaultdict(list)
    diagnostic_components: dict[str, list[float]] = defaultdict(list)
    arena_accumulators: dict[str, list[_ArenaPerformanceSample]] = defaultdict(list)
    artifact_errors: list[str] = []
    artifact_match_count = 0

    for record in record_rows:
        artifact_path = _successful_artifact_path(record)
        if artifact_path is None:
            continue
        try:
            payload = json.loads(artifact_path.read_text(encoding="utf-8"))
            result = payload["result"]
            traces = result["traces"]
        except (OSError, KeyError, TypeError, json.JSONDecodeError) as exc:
            artifact_errors.append(f"{artifact_path}: {type(exc).__name__}: {exc}")
            continue
        if not isinstance(result, dict) or not isinstance(traces, list):
            artifact_errors.append(f"{artifact_path}: invalid result/traces structure")
            continue

        artifact_match_count += 1
        turn_keys = {
            (trace.get("round_number"), trace.get("turn_index"), trace.get("actor_uuid"))
            for trace in traces
            if isinstance(trace, dict)
        }
        elapsed_ms = _number(result.get("elapsed_ms")) or 0.0
        command_count = int(_number(result.get("command_count")) or len(traces))
        final_round = _number(result.get("final_round")) or 0.0
        arena_accumulators[str(result.get("arena_id") or record.schedule_entry.arena_id)].append(
            _ArenaPerformanceSample(
                elapsed_ms=elapsed_ms,
                command_count=command_count,
                actor_turn_count=len(turn_keys),
                final_round=final_round,
                side_order=record.schedule_entry.side_order_id,
            )
        )

        for trace in traces:
            if not isinstance(trace, dict):
                continue
            for field in (*CLIENT_STAGE_FIELDS, "total_ms"):
                value = _number(trace.get(field))
                if value is not None:
                    client_samples[field].append(value)
            server_timing = trace.get("server_timing")
            action_timing = trace.get("action_server_timing")
            _collect_timing_phases(server_timing, server_phase_samples)
            _collect_timing_phases(action_timing, engine_phase_samples)
            _collect_diagnostic_components(server_timing, action_timing, diagnostic_components)

    total_elapsed_ms = sum(match_elapsed)
    total_commands = sum(base_commands)
    arena_rows = [_arena_performance(arena_id, rows) for arena_id, rows in sorted(arena_accumulators.items())]
    total_actor_turns = sum(row.actor_turn_count for row in arena_rows)
    evaluation_wall_elapsed_ms = _elapsed_window_ms(
        evaluation_started_at,
        evaluation_completed_at,
    )
    evaluator_overhead_ms = (
        round(max(0.0, evaluation_wall_elapsed_ms - total_elapsed_ms), 3)
        if evaluation_wall_elapsed_ms is not None
        else None
    )
    final_round_values = [
        row.final_round
        for rows in arena_accumulators.values()
        for row in rows
    ]
    total_traced_ms = sum(client_samples["total_ms"])
    client_stage_share = {
        field: round(100.0 * sum(client_samples[field]) / total_traced_ms, 3)
        for field in CLIENT_STAGE_FIELDS
        if client_samples[field] and total_traced_ms > 0
    }
    accounted_ms = sum(sum(client_samples[field]) for field in CLIENT_STAGE_FIELDS)
    unaccounted_samples = _unaccounted_command_samples(client_samples)
    if unaccounted_samples:
        client_samples["other_client_overhead_ms"].extend(unaccounted_samples)
        client_stage_share["other_client_overhead_ms"] = round(
            100.0 * max(0.0, total_traced_ms - accounted_ms) / total_traced_ms,
            3,
        )

    return EloRuntimePerformance(
        match_count=len(match_elapsed),
        artifact_match_count=artifact_match_count,
        artifact_errors=artifact_errors,
        evaluation_wall_elapsed_ms=evaluation_wall_elapsed_ms,
        evaluator_overhead_ms=evaluator_overhead_ms,
        simulation_time_share_pct=(
            round(100.0 * total_elapsed_ms / evaluation_wall_elapsed_ms, 3)
            if evaluation_wall_elapsed_ms
            else None
        ),
        wall_matches_per_minute=(
            round(60_000.0 * len(match_elapsed) / evaluation_wall_elapsed_ms, 3)
            if evaluation_wall_elapsed_ms
            else None
        ),
        wall_commands_per_second=(
            round(1000.0 * total_commands / evaluation_wall_elapsed_ms, 3)
            if evaluation_wall_elapsed_ms
            else None
        ),
        wall_actor_turns_per_second=(
            round(1000.0 * total_actor_turns / evaluation_wall_elapsed_ms, 3)
            if evaluation_wall_elapsed_ms
            else None
        ),
        total_elapsed_ms=round(total_elapsed_ms, 3),
        average_elapsed_ms=_rounded_mean(match_elapsed),
        p95_elapsed_ms=_rounded_percentile(match_elapsed, 0.95),
        max_elapsed_ms=round(max(match_elapsed), 3) if match_elapsed else None,
        total_command_count=total_commands,
        average_command_count=_rounded_mean([float(value) for value in base_commands]),
        total_actor_turn_count=total_actor_turns,
        average_actor_turn_count=(
            round(total_actor_turns / artifact_match_count, 3)
            if artifact_match_count
            else None
        ),
        average_final_round=_rounded_mean(final_round_values),
        commands_per_second=(
            round(total_commands / (total_elapsed_ms / 1000.0), 3)
            if total_elapsed_ms > 0
            else None
        ),
        actor_turns_per_second=(
            round(total_actor_turns / (total_elapsed_ms / 1000.0), 3)
            if total_elapsed_ms > 0
            else None
        ),
        traced_command_ms=_distribution(client_samples["total_ms"]),
        client_stage_ms={
            field: _distribution(client_samples[field])
            for field in (*CLIENT_STAGE_FIELDS, "other_client_overhead_ms")
            if client_samples[field]
        },
        client_stage_share_pct=client_stage_share,
        diagnostic_components_ms={
            name: _distribution(values)
            for name, values in sorted(diagnostic_components.items())
            if values
        },
        top_server_phases_ms=_top_phase_distributions(server_phase_samples),
        top_engine_phases_ms=_top_phase_distributions(engine_phase_samples),
        arenas=arena_rows,
    )


def _elapsed_window_ms(
    started_at: Optional[str],
    completed_at: Optional[str],
) -> Optional[float]:
    if started_at is None or completed_at is None:
        return None
    try:
        elapsed = (
            datetime.fromisoformat(completed_at) - datetime.fromisoformat(started_at)
        ).total_seconds() * 1000.0
    except ValueError:
        return None
    return round(elapsed, 3) if elapsed >= 0 else None


def _successful_artifact_path(record: EloMatchRecord) -> Optional[Path]:
    for raw_path in record.artifact_paths:
        path = Path(raw_path)
        if path.name.endswith(".failure.json"):
            continue
        return path
    return None


def _collect_timing_phases(
    timing: object,
    destination: dict[str, list[float]],
) -> None:
    if not isinstance(timing, dict):
        return
    phases = timing.get("phases")
    if not isinstance(phases, dict):
        return
    for name, raw_value in phases.items():
        value = _number(raw_value)
        if value is not None:
            destination[str(name)].append(value)


def _collect_diagnostic_components(
    server_timing: object,
    action_timing: object,
    destination: dict[str, list[float]],
) -> None:
    _append_timing_value(destination, "server_command_total_ms", server_timing, "total_ms")
    _append_timing_value(destination, "engine_action_total_ms", action_timing, "total_ms")
    _append_phase_value(
        destination,
        "decision_epoch_build_ms",
        server_timing,
        "publish.followup_epoch.build_decision_epoch_total_ms",
    )
    _append_phase_value(
        destination,
        "available_actions_ms",
        server_timing,
        "publish.followup_epoch.get_available_actions_ms",
    )
    _append_phase_value(
        destination,
        "affordance_serialization_ms",
        server_timing,
        "publish.followup_epoch.build_affordance_set_ms",
    )
    _append_phase_value(destination, "engine_execute_by_index_ms", action_timing, "execute_by_index_ms")
    _append_phase_value(
        destination,
        "engine_observation_projection_ms",
        action_timing,
        "execute_by_index.observation_projection.projection.project_events_ms",
    )
    _append_phase_value(
        destination,
        "engine_senses_ms",
        action_timing,
        "execute_by_index.event_queue.pre_completion.callback.SpatialSensesSystem_ms",
    )


def _append_timing_value(
    destination: dict[str, list[float]],
    label: str,
    timing: object,
    key: str,
) -> None:
    if not isinstance(timing, dict):
        return
    value = _number(timing.get(key))
    if value is not None:
        destination[label].append(value)


def _append_phase_value(
    destination: dict[str, list[float]],
    label: str,
    timing: object,
    phase: str,
) -> None:
    if not isinstance(timing, dict):
        return
    phases = timing.get("phases")
    if not isinstance(phases, dict):
        return
    value = _number(phases.get(phase))
    if value is not None:
        destination[label].append(value)


def _arena_performance(
    arena_id: str,
    rows: list[_ArenaPerformanceSample],
) -> EloArenaPerformance:
    elapsed_values = [row.elapsed_ms for row in rows]
    command_count = sum(row.command_count for row in rows)
    actor_turn_count = sum(row.actor_turn_count for row in rows)
    elapsed_seconds = sum(elapsed_values) / 1000.0
    side_orders = Counter(row.side_order for row in rows)
    return EloArenaPerformance(
        arena_id=arena_id,
        match_count=len(rows),
        command_count=command_count,
        actor_turn_count=actor_turn_count,
        side_order_counts=dict(sorted(side_orders.items())),
        match_elapsed_ms=_distribution(elapsed_values),
        commands_per_match=round(command_count / len(rows), 3),
        actor_turns_per_match=round(actor_turn_count / len(rows), 3),
        final_round_per_match=round(fmean(row.final_round for row in rows), 3),
        commands_per_second=round(command_count / elapsed_seconds, 3) if elapsed_seconds else 0.0,
        actor_turns_per_second=round(actor_turn_count / elapsed_seconds, 3) if elapsed_seconds else 0.0,
    )


def _unaccounted_command_samples(samples: dict[str, list[float]]) -> list[float]:
    sample_count = len(samples["total_ms"])
    if not sample_count or any(len(samples[field]) != sample_count for field in CLIENT_STAGE_FIELDS):
        return []
    return [
        max(
            0.0,
            samples["total_ms"][index]
            - sum(samples[field][index] for field in CLIENT_STAGE_FIELDS),
        )
        for index in range(sample_count)
    ]


def _top_phase_distributions(
    samples: dict[str, list[float]],
    *,
    limit: int = 25,
) -> dict[str, EloMetricDistribution]:
    names = sorted(samples, key=lambda name: (-sum(samples[name]), name))[:limit]
    return {name: _distribution(samples[name]) for name in names}


def _distribution(values: list[float]) -> EloMetricDistribution:
    if not values:
        return EloMetricDistribution(
            count=0,
            total=0.0,
            minimum=0.0,
            mean=0.0,
            median=0.0,
            p95=0.0,
            p99=0.0,
            maximum=0.0,
        )
    ordered = sorted(values)
    return EloMetricDistribution(
        count=len(ordered),
        total=round(sum(ordered), 3),
        minimum=round(ordered[0], 3),
        mean=round(fmean(ordered), 3),
        median=round(median(ordered), 3),
        p95=round(_nearest_rank(ordered, 0.95), 3),
        p99=round(_nearest_rank(ordered, 0.99), 3),
        maximum=round(ordered[-1], 3),
    )


def _rounded_mean(values: list[float]) -> Optional[float]:
    return round(fmean(values), 3) if values else None


def _rounded_percentile(values: list[float], percentile: float) -> Optional[float]:
    return round(_nearest_rank(sorted(values), percentile), 3) if values else None


def _nearest_rank(ordered: list[float], percentile: float) -> float:
    index = max(0, min(len(ordered) - 1, math.ceil(len(ordered) * percentile) - 1))
    return ordered[index]


def _number(value: object) -> Optional[float]:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)
