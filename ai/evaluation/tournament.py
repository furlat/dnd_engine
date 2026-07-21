"""Tournament and Elo summaries for AI-vs-AI validation runs."""

from __future__ import annotations

from datetime import datetime, timezone
import math
from pathlib import Path
from typing import Literal, Optional
from uuid import uuid4

from pydantic import BaseModel, Field

from ai.evaluation.artifacts import audit_external_selfplay_subjectivity, build_external_selfplay_artifact, write_validation_run_artifact
from ai.external_selfplay import ExternalSelfPlayResult, run_external_selfplay


Outcome = Literal["heroes", "monsters", "draw", "unknown"]


class EloConfig(BaseModel):
    """Configuration for setup-rating updates."""

    initial_rating: float = Field(default=1000.0, description="Initial rating assigned to unseen participants.")
    k_factor: float = Field(default=32.0, description="Elo K factor used for every match.")


class TournamentMatchRecord(BaseModel):
    """One completed match in a tournament schedule."""

    match_id: str = Field(description="Stable match identifier.")
    arena_id: str = Field(description="Arena used for the match.")
    random_seed: Optional[int] = Field(default=None, description="Random seed used for the run.")
    hero_first: bool = Field(description="Whether the hero side was prioritized to open the encounter.")
    status: str = Field(description="Self-play runner status.")
    command_count: int = Field(description="Number of selected commands.")
    elapsed_ms: float = Field(description="Runner wall-clock duration in milliseconds.")
    outcome: Outcome = Field(description="Match outcome from final faction HP.")
    faction_hp: dict[str, int] = Field(default_factory=dict, description="Final total HP by faction.")
    command_status_counts: dict[str, int] = Field(default_factory=dict, description="Command-result counts from retained traces.")
    subjectivity_status: Literal["not_run", "passed", "failed"] = Field(
        default="not_run",
        description="Disclosure audit status derived from retained subjective traces.",
    )
    subjectivity_violation_count: int = Field(default=0, description="Number of disclosure audit violations.")
    max_command_total_ms: Optional[float] = Field(default=None, description="Largest per-command total latency when traced.")
    max_server_command_ms: Optional[float] = Field(default=None, description="Largest server-side command latency when traced.")
    max_local_decision_ms: Optional[float] = Field(default=None, description="Largest local decision latency when traced.")
    command_total_samples_ms: list[float] = Field(default_factory=list, description="Per-command total latency samples in milliseconds.")
    server_command_samples_ms: list[float] = Field(default_factory=list, description="Per-command server latency samples in milliseconds.")
    local_decision_samples_ms: list[float] = Field(default_factory=list, description="Per-command local decision latency samples in milliseconds.")
    normal_command_total_samples_ms: list[float] = Field(default_factory=list, description="Total latency samples for commands without deep diagnostic probes.")
    normal_server_command_samples_ms: list[float] = Field(default_factory=list, description="Server latency samples for commands without deep diagnostic probes.")
    normal_local_decision_samples_ms: list[float] = Field(default_factory=list, description="Local decision samples for commands without deep diagnostic probes.")
    diagnostic_command_total_samples_ms: list[float] = Field(default_factory=list, description="Total latency samples for deep diagnostic probe commands.")
    diagnostic_server_command_samples_ms: list[float] = Field(default_factory=list, description="Server latency samples for deep diagnostic probe commands.")
    diagnostic_local_decision_samples_ms: list[float] = Field(default_factory=list, description="Local decision samples for deep diagnostic probe commands.")
    stage_samples_ms: dict[str, list[float]] = Field(
        default_factory=dict,
        description="Per-command latency samples grouped by named runtime stage.",
    )
    normal_stage_samples_ms: dict[str, list[float]] = Field(
        default_factory=dict,
        description="Per-stage latency samples for commands without deep diagnostic probes.",
    )
    diagnostic_stage_samples_ms: dict[str, list[float]] = Field(
        default_factory=dict,
        description="Per-stage latency samples for deep diagnostic probe commands.",
    )
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
    rating_before: dict[str, float] = Field(default_factory=dict, description="Ratings before this match.")
    rating_after: dict[str, float] = Field(default_factory=dict, description="Ratings after this match.")
    rating_delta: dict[str, float] = Field(default_factory=dict, description="Rating movement caused by this match.")
    run_artifact_path: Optional[str] = Field(default=None, description="Optional raw run artifact path.")


class RatingSnapshot(BaseModel):
    """Participant rating after a match."""

    match_index: int = Field(description="Zero-based match index.")
    match_id: str = Field(description="Match that produced this rating.")
    participant_id: str = Field(description="Rated participant id.")
    rating: float = Field(description="Rating after the match.")


class TournamentSummary(BaseModel):
    """Durable tournament summary consumed by dashboards."""

    schema_version: Literal[1] = Field(default=1, description="Tournament summary schema version.")
    tournament_id: str = Field(description="Stable tournament identifier.")
    generated_at: str = Field(description="UTC timestamp when the tournament finished.")
    elo_config: EloConfig = Field(description="Rating configuration used for updates.")
    arena_ids: list[str] = Field(description="Arena schedule roots.")
    matches: list[TournamentMatchRecord] = Field(default_factory=list, description="Completed match records.")
    ratings: dict[str, float] = Field(default_factory=dict, description="Final ratings keyed by participant id.")
    rating_series: list[RatingSnapshot] = Field(default_factory=list, description="Per-match rating time series.")


def run_ai_tournament(
    arena_ids: list[str],
    *,
    seeds: list[int],
    max_commands: int = 80,
    hero_first_alternates: bool = True,
    elo_config: Optional[EloConfig] = None,
    runs_output_directory: Optional[Path | str] = None,
    tournament_output_directory: Optional[Path | str] = "ai/evidence/tournaments",
) -> TournamentSummary:
    """Run a structured AI-vs-AI tournament over validation arenas.

    Args:
        arena_ids: Arena ids to play.
        seeds: Random seeds played for every arena.
        max_commands: Command cap per match.
        hero_first_alternates: Whether odd schedule rows let monsters open.
        elo_config: Optional rating configuration.
        runs_output_directory: Optional directory for raw run artifacts.
        tournament_output_directory: Optional directory for tournament summary
            JSON. When provided, also updates `latest.json`.

    Returns:
        Durable tournament summary.
    """
    config = elo_config or EloConfig()
    tournament_id = _new_tournament_id()
    summary = TournamentSummary(
        tournament_id=tournament_id,
        generated_at=datetime.now(timezone.utc).isoformat(),
        elo_config=config,
        arena_ids=list(arena_ids),
    )
    ratings: dict[str, float] = {}
    match_index = 0
    for arena_id in arena_ids:
        for seed_index, seed in enumerate(seeds):
            hero_first = True if not hero_first_alternates else seed_index % 2 == 0
            result = run_external_selfplay(
                arena_id,
                max_commands=max_commands,
                hero_first=hero_first,
                random_seed=seed,
            )
            run_artifact_path: Optional[str] = None
            if runs_output_directory is not None:
                artifact = build_external_selfplay_artifact(
                    result,
                    run_id=f"{tournament_id}-{match_index:04d}-{arena_id}",
                    random_seed=seed,
                )
                run_artifact_path = str(write_validation_run_artifact(artifact, runs_output_directory))
            record = build_tournament_match_record(
                result,
                match_id=f"{tournament_id}-{match_index:04d}",
                random_seed=seed,
                hero_first=hero_first,
                ratings=ratings,
                elo_config=config,
                run_artifact_path=run_artifact_path,
            )
            summary.matches.append(record)
            ratings.update(record.rating_after)
            for participant_id, rating in sorted(ratings.items()):
                summary.rating_series.append(
                    RatingSnapshot(
                        match_index=match_index,
                        match_id=record.match_id,
                        participant_id=participant_id,
                        rating=round(rating, 3),
                    )
                )
            match_index += 1
    summary.ratings = {participant_id: round(rating, 3) for participant_id, rating in sorted(ratings.items())}
    if tournament_output_directory is not None:
        write_tournament_summary(summary, tournament_output_directory)
    return summary


def build_tournament_match_record(
    result: ExternalSelfPlayResult,
    *,
    match_id: str,
    random_seed: Optional[int],
    hero_first: bool,
    ratings: dict[str, float],
    elo_config: EloConfig,
    run_artifact_path: Optional[str] = None,
) -> TournamentMatchRecord:
    """Build a tournament record and rating update from one run result."""
    hero_id = f"{result.arena_id}::heroes"
    monster_id = f"{result.arena_id}::monsters"
    before = {
        hero_id: ratings.get(hero_id, elo_config.initial_rating),
        monster_id: ratings.get(monster_id, elo_config.initial_rating),
    }
    faction_hp = final_hp_by_faction(result)
    outcome = outcome_from_faction_hp(faction_hp)
    subjectivity = audit_external_selfplay_subjectivity(result)
    hero_score, monster_score = _scores_for_outcome(outcome)
    hero_after, monster_after = update_elo_pair(
        before[hero_id],
        before[monster_id],
        hero_score,
        monster_score,
        k_factor=elo_config.k_factor,
    )
    after = {hero_id: hero_after, monster_id: monster_after}
    command_total_samples = _trace_ms_values(result, "total_ms")
    server_command_samples = _trace_server_ms_values(result)
    local_decision_samples = _trace_ms_values(result, "local_decision_ms")
    normal_command_total_samples = _trace_ms_values(result, "total_ms", deep_diagnostics_enabled=False)
    normal_server_command_samples = _trace_server_ms_values(result, deep_diagnostics_enabled=False)
    normal_local_decision_samples = _trace_ms_values(result, "local_decision_ms", deep_diagnostics_enabled=False)
    diagnostic_command_total_samples = _trace_ms_values(result, "total_ms", deep_diagnostics_enabled=True)
    diagnostic_server_command_samples = _trace_server_ms_values(result, deep_diagnostics_enabled=True)
    diagnostic_local_decision_samples = _trace_ms_values(result, "local_decision_ms", deep_diagnostics_enabled=True)
    stage_samples = _trace_stage_samples(result)
    normal_stage_samples = _trace_stage_samples(result, deep_diagnostics_enabled=False)
    diagnostic_stage_samples = _trace_stage_samples(result, deep_diagnostics_enabled=True)
    return TournamentMatchRecord(
        match_id=match_id,
        arena_id=result.arena_id,
        random_seed=random_seed,
        hero_first=hero_first,
        status=result.status,
        command_count=result.command_count,
        elapsed_ms=round(result.elapsed_ms, 3),
        outcome=outcome,
        faction_hp=faction_hp,
        command_status_counts=_command_status_counts(result),
        subjectivity_status=subjectivity.status,
        subjectivity_violation_count=len(subjectivity.violations),
        max_command_total_ms=_max_ms(command_total_samples),
        max_server_command_ms=_max_ms(server_command_samples),
        max_local_decision_ms=_max_ms(local_decision_samples),
        command_total_samples_ms=command_total_samples,
        server_command_samples_ms=server_command_samples,
        local_decision_samples_ms=local_decision_samples,
        normal_command_total_samples_ms=normal_command_total_samples,
        normal_server_command_samples_ms=normal_server_command_samples,
        normal_local_decision_samples_ms=normal_local_decision_samples,
        diagnostic_command_total_samples_ms=diagnostic_command_total_samples,
        diagnostic_server_command_samples_ms=diagnostic_server_command_samples,
        diagnostic_local_decision_samples_ms=diagnostic_local_decision_samples,
        stage_samples_ms=stage_samples,
        normal_stage_samples_ms=normal_stage_samples,
        diagnostic_stage_samples_ms=diagnostic_stage_samples,
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
        rating_before={participant_id: round(value, 3) for participant_id, value in before.items()},
        rating_after={participant_id: round(value, 3) for participant_id, value in after.items()},
        rating_delta={
            participant_id: round(after[participant_id] - before[participant_id], 3)
            for participant_id in before
        },
        run_artifact_path=run_artifact_path,
    )


def final_hp_by_faction(result: ExternalSelfPlayResult) -> dict[str, int]:
    """Derive final HP totals by faction from self-play traces."""
    faction_by_actor_name: dict[str, str] = dict(result.final_faction_by_actor)
    for trace in result.traces:
        if trace.actor_faction is not None:
            faction_by_actor_name.setdefault(trace.actor_name, trace.actor_faction)
    totals: dict[str, int] = {}
    for actor_name, hp in result.final_hp_by_actor.items():
        faction = faction_by_actor_name.get(actor_name)
        if faction is None:
            continue
        totals[faction] = totals.get(faction, 0) + max(0, hp)
    return totals


def outcome_from_faction_hp(faction_hp: dict[str, int]) -> Outcome:
    """Return a compact outcome from final faction HP totals."""
    hero_hp = faction_hp.get("heroes")
    monster_hp = faction_hp.get("monsters")
    if hero_hp is None or monster_hp is None:
        return "unknown"
    if hero_hp <= 0 and monster_hp <= 0:
        return "draw"
    if hero_hp > 0 and monster_hp <= 0:
        return "heroes"
    if monster_hp > 0 and hero_hp <= 0:
        return "monsters"
    if hero_hp == monster_hp:
        return "draw"
    return "heroes" if hero_hp > monster_hp else "monsters"


def _command_status_counts(result: ExternalSelfPlayResult) -> dict[str, int]:
    counts: dict[str, int] = {}
    for trace in result.traces:
        status = trace.command_status or "missing_result"
        counts[status] = counts.get(status, 0) + 1
    return dict(sorted(counts.items()))


def _trace_ms_values(
    result: ExternalSelfPlayResult,
    field_name: str,
    *,
    deep_diagnostics_enabled: Optional[bool] = None,
) -> list[float]:
    return [
        round(float(value), 3)
        for trace in result.traces
        if (deep_diagnostics_enabled is None or trace.deep_diagnostics_enabled is deep_diagnostics_enabled)
        if (value := getattr(trace, field_name)) is not None
    ]


def _trace_server_ms_values(
    result: ExternalSelfPlayResult,
    *,
    deep_diagnostics_enabled: Optional[bool] = None,
) -> list[float]:
    values: list[float] = []
    for trace in result.traces:
        if deep_diagnostics_enabled is not None and trace.deep_diagnostics_enabled is not deep_diagnostics_enabled:
            continue
        value = trace.server_timing.get("total_ms")
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            values.append(round(float(value), 3))
    return values


TRACE_LATENCY_STAGE_FIELDS = (
    "snapshot_ms",
    "materialize_ms",
    "frame_fetch_ms",
    "frame_apply_ms",
    "pre_command_sync_ms",
    "pre_command_frame_fetch_ms",
    "pre_command_frame_apply_ms",
    "followup_frame_fetch_ms",
    "followup_frame_apply_ms",
    "command_followup_sync_ms",
    "reduce_ms",
    "fact_ms",
    "policy_ms",
    "local_decision_ms",
    "command_http_ms",
    "command_submit_ms",
    "total_ms",
)


def _trace_stage_samples(
    result: ExternalSelfPlayResult,
    *,
    deep_diagnostics_enabled: Optional[bool] = None,
) -> dict[str, list[float]]:
    samples: dict[str, list[float]] = {}
    for trace in result.traces:
        if deep_diagnostics_enabled is not None and trace.deep_diagnostics_enabled is not deep_diagnostics_enabled:
            continue
        for field_name in TRACE_LATENCY_STAGE_FIELDS:
            value = getattr(trace, field_name)
            if value is None:
                continue
            samples.setdefault(field_name, []).append(round(float(value), 3))
        _append_timing_phase_samples(samples, "server", trace.server_timing)
        _append_timing_phase_samples(samples, "engine", trace.action_server_timing)
    return {
        stage_name: values
        for stage_name, values in sorted(samples.items())
        if values
    }


def _append_timing_phase_samples(
    samples: dict[str, list[float]],
    prefix: str,
    timing_payload: dict[str, object],
) -> None:
    """Append nested timing phases using an explicit summary-stage prefix."""
    phases = timing_payload.get("phases")
    if not isinstance(phases, dict):
        return
    for phase_name, value in phases.items():
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            continue
        samples.setdefault(f"{prefix}.{phase_name}", []).append(round(float(value), 3))


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


def update_elo_pair(
    rating_a: float,
    rating_b: float,
    score_a: float,
    score_b: float,
    *,
    k_factor: float,
) -> tuple[float, float]:
    """Return updated Elo ratings for a two-participant result."""
    expected_a = 1.0 / (1.0 + 10 ** ((rating_b - rating_a) / 400.0))
    expected_b = 1.0 - expected_a
    return (
        rating_a + k_factor * (score_a - expected_a),
        rating_b + k_factor * (score_b - expected_b),
    )


def write_tournament_summary(summary: TournamentSummary, output_directory: Path | str) -> Path:
    """Persist tournament summary JSON and update a `latest.json` pointer."""
    directory = Path(output_directory)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{summary.tournament_id}.json"
    with path.open("x", encoding="utf-8") as handle:
        handle.write(summary.model_dump_json(indent=2))
        handle.write("\n")
    latest = directory / "latest.json"
    latest.write_text(summary.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return path


def _scores_for_outcome(outcome: Outcome) -> tuple[float, float]:
    """Map match outcome to Elo scores."""
    if outcome == "heroes":
        return 1.0, 0.0
    if outcome == "monsters":
        return 0.0, 1.0
    return 0.5, 0.5


def _new_tournament_id() -> str:
    """Build a readable unique tournament id."""
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{timestamp}-ai-tournament-{uuid4().hex[:8]}"
