"""Retained-data analysis for disposable-worker parallel scaling pilots."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ScalingPilot(BaseModel):
    """Measured execution of one comparable tournament workload."""

    model_config = ConfigDict(frozen=True)

    worker_count: int = Field(ge=1, description="Maximum concurrent disposable workers.")
    workload_hash: str = Field(description="Hash proving pilots executed identical schedule rows.")
    scheduled_matches: int = Field(ge=1, description="Matches in the comparable pilot workload.")
    completed_matches: int = Field(ge=0, description="Matches with retained terminal receipts.")
    eligible_matches: int = Field(ge=0, description="Matches admitted to scientific analysis.")
    wall_seconds: float = Field(gt=0, description="Coordinator wall-clock duration in seconds.")
    total_worker_cpu_seconds: float = Field(ge=0, description="Sum of worker user and system CPU seconds.")
    peak_rss_mb: float = Field(ge=0, description="Largest measured peak RSS of any disposable worker in MiB.")
    failure_count: int = Field(ge=0, description="Worker or scientific failures observed.")
    determinism_canaries_passed: bool = Field(description="Whether repeated semantic-result hashes matched.")


class ScalingRow(BaseModel):
    """Derived scaling metrics for one worker count."""

    model_config = ConfigDict(frozen=True)

    worker_count: int = Field(ge=1, description="Concurrent worker limit.")
    wall_seconds: float = Field(gt=0, description="Measured wall duration in seconds.")
    matches_per_second: float = Field(ge=0, description="Completed match throughput.")
    speedup: float = Field(gt=0, description="Speedup relative to the single-worker pilot.")
    parallel_efficiency: float = Field(gt=0, description="Speedup divided by worker count.")
    cpu_utilization_equivalent: float = Field(ge=0, description="Worker CPU seconds divided by wall seconds.")
    peak_rss_mb: float = Field(ge=0, description="Largest measured individual-worker peak RSS in MiB.")
    rss_per_worker_mb: float = Field(ge=0, description="Largest measured individual-worker peak RSS in MiB.")
    failure_rate: float = Field(ge=0, le=1, description="Failures divided by scheduled matches.")
    determinism_canaries_passed: bool = Field(description="Whether determinism checks passed.")


class ParallelScalingAnalysis(BaseModel):
    """Comparable pilot scaling curve and selected production concurrency."""

    model_config = ConfigDict(frozen=True)

    schema_version: Literal[1] = Field(default=1, description="Scaling analysis schema version.")
    comparable_workload_hash: str = Field(description="Shared pilot workload hash.")
    baseline_worker_count: Literal[1] = Field(default=1, description="Reference worker count.")
    rows: tuple[ScalingRow, ...] = Field(description="Scaling rows ordered by worker count.")
    selected_worker_count: int = Field(ge=1, description="Measured production concurrency selection.")
    selection_reason: str = Field(description="Deterministic explanation for the selected worker count.")


def analyze_parallel_scaling(pilots: tuple[ScalingPilot, ...]) -> ParallelScalingAnalysis:
    """Calculate speedup and choose production concurrency from retained pilots.

    Args:
        pilots: Comparable measurements including a single-worker baseline.

    Returns:
        Scaling curve and deterministic production-worker recommendation.

    Raises:
        ValueError: If pilots are missing, duplicated, or incomparable.
    """
    if not pilots:
        raise ValueError("At least one scaling pilot is required.")
    workload_hashes = {row.workload_hash for row in pilots}
    if len(workload_hashes) != 1:
        raise ValueError("Scaling pilots must execute the same workload hash.")
    worker_counts = [row.worker_count for row in pilots]
    if len(worker_counts) != len(set(worker_counts)):
        raise ValueError("Scaling pilots must use unique worker counts.")
    baseline = next((row for row in pilots if row.worker_count == 1), None)
    if baseline is None:
        raise ValueError("Scaling analysis requires a single-worker baseline.")
    rows = []
    for pilot in sorted(pilots, key=lambda row: row.worker_count):
        speedup = baseline.wall_seconds / pilot.wall_seconds
        throughput = pilot.completed_matches / pilot.wall_seconds
        rows.append(ScalingRow(
            worker_count=pilot.worker_count,
            wall_seconds=pilot.wall_seconds,
            matches_per_second=throughput,
            speedup=speedup,
            parallel_efficiency=speedup / pilot.worker_count,
            cpu_utilization_equivalent=pilot.total_worker_cpu_seconds / pilot.wall_seconds,
            peak_rss_mb=pilot.peak_rss_mb,
            rss_per_worker_mb=pilot.peak_rss_mb,
            failure_rate=pilot.failure_count / pilot.scheduled_matches,
            determinism_canaries_passed=pilot.determinism_canaries_passed,
        ))
    eligible = [
        row
        for row in rows
        if row.failure_rate == 0.0 and row.determinism_canaries_passed
    ]
    if not eligible:
        selected = rows[0]
        reason = "No pilot passed failure and determinism gates; retain the single-worker baseline."
    else:
        selected = max(eligible, key=lambda row: (row.matches_per_second, -row.peak_rss_mb, -row.worker_count))
        reason = (
            f"Selected {selected.worker_count} workers because it delivered the highest measured clean "
            f"throughput ({selected.matches_per_second:.3f} matches/s) with passing determinism canaries."
        )
    return ParallelScalingAnalysis(
        comparable_workload_hash=next(iter(workload_hashes)),
        rows=tuple(rows),
        selected_worker_count=selected.worker_count,
        selection_reason=reason,
    )
