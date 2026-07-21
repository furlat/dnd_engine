"""Deterministic projection of validation artifacts into dashboard statistics."""

from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
import json
import math
from pathlib import Path
from statistics import fmean, median
from typing import Any, Iterable, Optional

from pydantic import BaseModel, Field

from ai.evaluation.artifacts import LatencyDistribution, ValidationRunArtifact
from ai.evaluation.direct_codex_artifacts import DirectCodexRunArtifact


DASHBOARD_SOURCE = (
    "AGENT_UX_ITERATION_LOG.md + evidence/runs/*.json + "
    "evidence/direct_codex_runs/*.json"
)
GENERATED_NOTE = (
    "Rows marked generated_from_artifact are deterministic projections of immutable "
    "run JSON; narrative findings remain human-authored."
)


class DashboardArtifactSource(BaseModel):
    """One validation artifact and its dashboard-relative path."""

    relative_path: str = Field(description="Artifact path relative to the ai directory.")
    content_sha256: str = Field(description="SHA-256 of the exact artifact file bytes.")
    artifact: ValidationRunArtifact = Field(description="Validated immutable run artifact.")


class DashboardDirectCodexSource(BaseModel):
    """One direct Codex artifact and its dashboard-relative path."""

    relative_path: str = Field(description="Artifact path relative to the ai directory.")
    content_sha256: str = Field(description="SHA-256 of the exact artifact file bytes.")
    artifact: DirectCodexRunArtifact = Field(description="Validated immutable direct Codex artifact.")


def load_artifact_sources(artifact_directory: Path | str) -> list[DashboardArtifactSource]:
    """Load validation artifacts in deterministic path order.

    Args:
        artifact_directory: Directory containing immutable run JSON files.

    Returns:
        Validated artifact sources sorted by dashboard-relative path.
    """
    directory = Path(artifact_directory)
    sources: list[DashboardArtifactSource] = []
    for path in sorted(directory.glob("*.json"), key=lambda candidate: candidate.name):
        content = path.read_bytes()
        artifact = ValidationRunArtifact.model_validate_json(content)
        if path.stem != artifact.run_id:
            raise ValueError(
                f"Artifact filename {path.name} does not match run id {artifact.run_id}"
            )
        sources.append(DashboardArtifactSource(
            relative_path=f"evidence/runs/{path.name}",
            content_sha256=sha256(content).hexdigest(),
            artifact=artifact,
        ))
    return sources


def load_direct_codex_sources(
    artifact_directory: Path | str,
) -> list[DashboardDirectCodexSource]:
    """Load direct Codex artifacts in deterministic path order.

    Args:
        artifact_directory: Directory containing immutable direct-run JSON files.

    Returns:
        Validated direct-run sources sorted by dashboard-relative path.
    """
    directory = Path(artifact_directory)
    sources: list[DashboardDirectCodexSource] = []
    for path in sorted(directory.glob("*.json"), key=lambda candidate: candidate.name):
        content = path.read_bytes()
        artifact = DirectCodexRunArtifact.model_validate_json(content)
        if path.stem != artifact.run_id:
            raise ValueError(
                f"Artifact filename {path.name} does not match run id {artifact.run_id}"
            )
        sources.append(DashboardDirectCodexSource(
            relative_path=f"evidence/direct_codex_runs/{path.name}",
            content_sha256=sha256(content).hexdigest(),
            artifact=artifact,
        ))
    return sources


def project_dashboard_stats(
    base_stats: dict[str, Any],
    artifact_sources: Iterable[DashboardArtifactSource],
    direct_codex_sources: Iterable[DashboardDirectCodexSource] = (),
) -> dict[str, Any]:
    """Return dashboard data with regenerated artifact-backed iterations.

    Existing generated iteration rows are discarded. Manual iterations,
    narrative findings, latest changes, and next targets remain unchanged.
    Machine-owned run rows are rebuilt exclusively from artifact bytes.

    Args:
        base_stats: Existing heterogeneous dashboard ledger.
        artifact_sources: Validated autonomous-run artifacts to project.
        direct_codex_sources: Validated direct Codex artifacts to project.

    Returns:
        Deep-copied dashboard data with deterministic generated rows.
    """
    projected = deepcopy(base_stats)
    raw_iterations = projected.get("iterations", [])
    if not isinstance(raw_iterations, list):
        raise ValueError("Dashboard statistics iterations must be a list")
    manual_iterations = [
        row
        for row in raw_iterations
        if isinstance(row, dict) and not bool(row.get("generated_from_artifact"))
    ]
    unique_sources = _unique_artifact_sources(artifact_sources)
    unique_direct_sources = _unique_direct_codex_sources(direct_codex_sources)
    _reject_cross_source_run_id_conflicts(unique_sources, unique_direct_sources)
    ordered_sources: list[
        tuple[str, DashboardArtifactSource | DashboardDirectCodexSource]
    ] = sorted(
        [(source.artifact.generated_at, source) for source in unique_sources]
        + [(source.artifact.captured_at, source) for source in unique_direct_sources],
        key=lambda row: (
            _parse_timestamp(row[0]),
            row[1].artifact.run_id,
            row[1].relative_path,
        ),
    )
    projected["schema_version"] = 2
    projected["projection"] = {
        "schema_version": 2,
        "projector": "ai.evaluation.dashboard_projection",
        "artifact_hash_algorithm": "sha256",
        "artifact_pattern": "evidence/runs/*.json",
        "artifact_patterns": [
            "evidence/runs/*.json",
            "evidence/direct_codex_runs/*.json",
        ],
        "run_count": len(ordered_sources),
        "autonomous_run_count": len(unique_sources),
        "direct_codex_run_count": len(unique_direct_sources),
    }
    projected["iterations"] = manual_iterations
    projected["runs"] = [
        (
            _projected_run(source, run_index)
            if isinstance(source, DashboardArtifactSource)
            else _projected_direct_codex_run(source, run_index)
        )
        for run_index, (_timestamp, source) in enumerate(ordered_sources, start=1)
    ]
    projected["source_log"] = DASHBOARD_SOURCE
    projected["source_artifacts"] = [
        source.relative_path
        for _timestamp, source in sorted(ordered_sources, key=lambda row: row[1].relative_path)
    ]
    notes = projected.get("notes", [])
    if not isinstance(notes, list):
        notes = []
    projected["notes"] = [*notes] if GENERATED_NOTE in notes else [*notes, GENERATED_NOTE]
    projected["updated_at"] = _latest_timestamp(
        projected.get("updated_at"),
        [timestamp for timestamp, _source in ordered_sources],
    )
    return projected


def write_projected_dashboard_stats(
    stats_path: Path | str,
    artifact_directory: Path | str,
    direct_codex_directory: Path | str | None = None,
) -> dict[str, Any]:
    """Regenerate artifact-backed rows and write stable formatted JSON.

    Args:
        stats_path: Existing dashboard statistics JSON path.
        artifact_directory: Directory containing autonomous-run artifacts.
        direct_codex_directory: Directory containing direct Codex artifacts.

    Returns:
        Projected dashboard dictionary written to disk.
    """
    path = Path(stats_path)
    base = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(base, dict):
        raise ValueError("Dashboard statistics root must be an object")
    direct_directory = (
        Path(direct_codex_directory)
        if direct_codex_directory is not None
        else Path(artifact_directory).parent / "direct_codex_runs"
    )
    projected = project_dashboard_stats(
        base,
        load_artifact_sources(artifact_directory),
        load_direct_codex_sources(direct_directory),
    )
    path.write_text(
        json.dumps(projected, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    return projected


def _projected_run(
    source: DashboardArtifactSource,
    run_index: int,
) -> dict[str, Any]:
    """Build one machine-owned run row from an immutable artifact."""
    artifact = source.artifact
    return {
        "run_index": run_index,
        "run_id": artifact.run_id,
        "generated_at": artifact.generated_at,
        "artifact": source.relative_path,
        "artifact_sha256": source.content_sha256,
        "artifact_schema_version": artifact.schema_version,
        "source_revision": artifact.source_revision,
        "random_seed": artifact.random_seed,
        "arena_id": artifact.arena_id,
        "controller_mode": artifact.controller_mode,
        "policy": artifact.policy.model_dump(mode="json"),
        "participants": [
            participant.model_dump(mode="json")
            for participant in artifact.participants
        ],
        "command_summary": artifact.command_summary.model_dump(mode="json"),
        "performance": artifact.performance.model_dump(mode="json"),
        "subjectivity": artifact.subjectivity.model_dump(mode="json"),
        "result": {
            "status": artifact.result.status,
            "command_count": artifact.result.command_count,
            "final_round": artifact.result.final_round,
            "final_state": artifact.result.final_state,
            "final_hp_by_actor": artifact.result.final_hp_by_actor,
        },
        "metrics": _artifact_metrics(artifact),
    }


def _projected_direct_codex_run(
    source: DashboardDirectCodexSource,
    run_index: int,
) -> dict[str, Any]:
    """Build one dashboard row from direct session-subjective evidence."""
    artifact = source.artifact
    command_summary = _direct_codex_command_summary(artifact)
    known_entities = {
        entity.uuid: entity
        for entity in artifact.initial_subjective_snapshot.known_entities
    }
    participants = [
        {
            "uuid": entity_uuid,
            "name": known_entities[entity_uuid].name if entity_uuid in known_entities else None,
            "faction": artifact.perspective.faction,
            "session_id": artifact.perspective.session_id,
            "controller_mode": artifact.perspective.controller_mode,
        }
        for entity_uuid in artifact.perspective.controlled_entity_uuids
    ]
    encounter_ended = any(
        frame.event_type == "encounter_end"
        for frame in artifact.observation_frames_response.frames
    )
    return {
        "run_index": run_index,
        "run_id": artifact.run_id,
        "generated_at": artifact.captured_at,
        "artifact": source.relative_path,
        "artifact_sha256": source.content_sha256,
        "artifact_schema_version": artifact.schema_version,
        "artifact_type": artifact.artifact_type,
        "source_revision": artifact.source_revision,
        "random_seed": None,
        "arena_id": artifact.rotation.arena_id,
        "controller_mode": artifact.perspective.controller_mode,
        "policy": None,
        "participants": participants,
        "command_summary": command_summary,
        "performance": None,
        "subjectivity": None,
        "result": {"status": "encounter_ended"} if encounter_ended else None,
        "metrics": _direct_codex_metrics(artifact, command_summary),
    }


def _direct_codex_command_summary(artifact: DirectCodexRunArtifact) -> dict[str, int]:
    """Count command outcomes present in the retained subjective frame stream."""
    results = {
        frame.command_result.command_id: frame.command_result
        for frame in artifact.observation_frames_response.frames
        if frame.command_result is not None
    }
    counts = Counter(result.status.value for result in results.values())
    submitted_ids = {
        command_id
        for row in artifact.agent_events_response.events
        if row.event.event_type == "command.submitted"
        and isinstance((command_id := row.event.payload.get("command_id")), str)
    }
    missing_result = len(submitted_ids - set(results))
    total = len(results) + missing_result
    return {
        "total": total,
        "accepted": counts["accepted"],
        "rejected": counts["rejected"],
        "stale": counts["stale"],
        "error": counts["error"],
        "missing_result": missing_result,
    }


def _direct_codex_metrics(
    artifact: DirectCodexRunArtifact,
    command_summary: dict[str, int],
) -> dict[str, Any]:
    """Derive only metrics explicitly supported by direct-run evidence."""
    nonaccepted = (
        command_summary["rejected"]
        + command_summary["stale"]
        + command_summary["error"]
        + command_summary["missing_result"]
    )
    metrics: dict[str, Any] = {
        "arena_id": artifact.rotation.arena_id,
        "mode": artifact.rotation.mode,
        "source_revision": artifact.source_revision,
        "artifact_schema_version": artifact.schema_version,
        "direct_codex_run_count": 1,
        "observation_frame_count": artifact.observation_frames_response.count,
        "agent_event_count": artifact.agent_events_response.count,
        "manual_friction_count": len(artifact.manual_friction),
        "accepted_commands": command_summary["accepted"],
        "nonaccepted_commands": nonaccepted,
        "direct_codex_accepted_commands": command_summary["accepted"],
        "direct_codex_nonaccepted_commands": nonaccepted,
    }
    friction_counts = Counter(annotation.category.value for annotation in artifact.manual_friction)
    for category, count in sorted(friction_counts.items()):
        metrics[f"friction_count_{_metric_token(category)}"] = count

    timing_payloads = [
        row.event.payload
        for row in artifact.agent_events_response.events
        if row.event.event_type == "runtime.command_timing"
    ]
    timing_fields = {
        "total_ms": "total_ms",
        "submit_http_ms": "command_submit_ms",
        "history_fetch_ms": "frame_fetch_ms",
        "history_apply_ms": "frame_apply_ms",
        "deferred_flush_ms": "deferred_flush_ms",
    }
    for payload_key, stage_name in timing_fields.items():
        values = _numeric_payload_values(timing_payloads, payload_key)
        if values:
            _add_stage_metrics(metrics, stage_name, _distribution(values))

    server_values = [
        float(server_timing["total_ms"])
        for payload in timing_payloads
        if isinstance((server_timing := payload.get("server_timing")), dict)
        and isinstance(server_timing.get("total_ms"), (int, float))
        and not isinstance(server_timing.get("total_ms"), bool)
    ]
    if server_values:
        _add_stage_metrics(metrics, "server_command_ms", _distribution(server_values))
    return metrics


def _numeric_payload_values(
    payloads: Iterable[dict[str, Any]],
    key: str,
) -> list[float]:
    """Return finite numeric samples for one telemetry payload key."""
    values: list[float] = []
    for payload in payloads:
        value = payload.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value):
            values.append(float(value))
    return values


def _distribution(values: list[float]) -> LatencyDistribution:
    """Build a rounded nearest-rank distribution from retained samples."""
    ordered = sorted(values)
    p95_index = max(0, math.ceil(0.95 * len(ordered)) - 1)
    return LatencyDistribution(
        count=len(ordered),
        min_ms=round(ordered[0], 3),
        mean_ms=round(fmean(ordered), 3),
        median_ms=round(float(median(ordered)), 3),
        p95_ms=round(ordered[p95_index], 3),
        max_ms=round(ordered[-1], 3),
    )


def _unique_artifact_sources(
    artifact_sources: Iterable[DashboardArtifactSource],
) -> list[DashboardArtifactSource]:
    """Deduplicate equal run identities and reject conflicting artifact bytes."""
    by_run_id: dict[str, DashboardArtifactSource] = {}
    for source in artifact_sources:
        run_id = source.artifact.run_id
        existing = by_run_id.get(run_id)
        if existing is None:
            by_run_id[run_id] = source
            continue
        if existing.content_sha256 != source.content_sha256:
            raise ValueError(
                f"Conflicting artifact content for run id {run_id}: "
                f"{existing.content_sha256} != {source.content_sha256}"
            )
        if source.relative_path < existing.relative_path:
            by_run_id[run_id] = source
    return list(by_run_id.values())


def _unique_direct_codex_sources(
    artifact_sources: Iterable[DashboardDirectCodexSource],
) -> list[DashboardDirectCodexSource]:
    """Deduplicate equal direct-run identities and reject conflicting bytes."""
    by_run_id: dict[str, DashboardDirectCodexSource] = {}
    for source in artifact_sources:
        run_id = source.artifact.run_id
        existing = by_run_id.get(run_id)
        if existing is None:
            by_run_id[run_id] = source
            continue
        if existing.content_sha256 != source.content_sha256:
            raise ValueError(
                f"Conflicting artifact content for run id {run_id}: "
                f"{existing.content_sha256} != {source.content_sha256}"
            )
        if source.relative_path < existing.relative_path:
            by_run_id[run_id] = source
    return list(by_run_id.values())


def _reject_cross_source_run_id_conflicts(
    autonomous_sources: Iterable[DashboardArtifactSource],
    direct_sources: Iterable[DashboardDirectCodexSource],
) -> None:
    """Reject a run id reused by different artifact schemas."""
    autonomous_ids = {source.artifact.run_id for source in autonomous_sources}
    direct_ids = {source.artifact.run_id for source in direct_sources}
    conflicts = sorted(autonomous_ids & direct_ids)
    if conflicts:
        raise ValueError(
            "Run ids cannot be shared by autonomous and direct artifacts: "
            + ", ".join(conflicts)
        )


def _artifact_metrics(artifact: ValidationRunArtifact) -> dict[str, Any]:
    """Derive dashboard metric names from raw artifact models and traces."""
    summary = artifact.command_summary
    result = artifact.result
    nonaccepted = summary.rejected + summary.stale + summary.error + summary.missing_result
    metrics: dict[str, Any] = {
        "arena_id": artifact.arena_id,
        "random_seed": artifact.random_seed,
        "mode": artifact.controller_mode,
        "source_revision": artifact.source_revision,
        "policy_name": artifact.policy.name,
        "policy_version": artifact.policy.version,
        "policy_source_hash": artifact.policy.source_hash,
        "artifact_schema_version": artifact.schema_version,
        "external_selfplay_batch_runs": 1,
        "external_selfplay_encounter_ended_runs": int(result.status == "encounter_ended"),
        "external_selfplay_command_cap_runs": int(result.status == "command_cap_reached"),
        "external_selfplay_command_rejected_runs": int(summary.rejected > 0),
        "external_selfplay_commands": summary.total,
        "external_selfplay_accepted_commands": summary.accepted,
        "external_selfplay_rejected_commands": summary.rejected,
        "external_selfplay_stale_commands": summary.stale,
        "external_selfplay_error_commands": summary.error,
        "external_selfplay_nonaccepted_commands": nonaccepted,
        "accepted_commands": summary.accepted,
        "nonaccepted_commands": nonaccepted,
        "external_selfplay_elapsed_ms": artifact.performance.elapsed_ms,
        "final_round": result.final_round,
        "subjectivity_audit_passed": int(artifact.subjectivity.status == "passed"),
        "subjectivity_violation_count": len(artifact.subjectivity.violations),
        "snapshot_loaded_count": sum(int(trace.snapshot_loaded) for trace in result.traces),
        "max_entity_action_count": max((trace.entity_action_count for trace in result.traces), default=0),
        "max_position_action_count": max((trace.position_action_count for trace in result.traces), default=0),
        "typed_routine_command_count": sum(int(trace.routine_id is not None) for trace in result.traces),
    }
    primary_stages = artifact.performance.normal_stages or artifact.performance.stages
    for stage_name, distribution in primary_stages.items():
        _add_stage_metrics(metrics, stage_name, distribution)
    for stage_name, distribution in artifact.performance.normal_stages.items():
        _add_stage_metrics(metrics, f"normal_{stage_name}", distribution)
    for stage_name, distribution in artifact.performance.diagnostic_stages.items():
        _add_stage_metrics(metrics, f"diagnostic_{stage_name}", distribution)

    total_max = _stage_stat(artifact, "total_ms", "max_ms")
    policy_max = _stage_stat(artifact, "policy_ms", "max_ms")
    if total_max is not None:
        metrics["max_command_total_ms"] = total_max
        metrics["total_command_max_ms"] = total_max
    if policy_max is not None:
        metrics["max_policy_tick_ms"] = policy_max
        metrics["max_policy_selection_ms"] = policy_max

    _add_trace_timing_metrics(metrics, artifact)
    tags = Counter(
        tag
        for trace in result.traces
        for tag in [*trace.logical_tags, *trace.outcome_logical_tags]
    )
    for tag, count in sorted(tags.items()):
        metrics[f"tag_count_{_metric_token(tag)}"] = count
    return metrics


def _add_stage_metrics(
    metrics: dict[str, Any],
    stage_name: str,
    distribution: LatencyDistribution,
) -> None:
    """Add stable count, percentile, and maximum keys for one stage."""
    prefix = stage_name.removesuffix("_ms")
    metrics[f"{prefix}_sample_count"] = distribution.count
    metrics[f"{prefix}_p95_ms"] = distribution.p95_ms
    metrics[f"{prefix}_max_ms"] = distribution.max_ms


def _add_trace_timing_metrics(
    metrics: dict[str, Any],
    artifact: ValidationRunArtifact,
) -> None:
    """Aggregate instrumented projection, reduction, and server subphases."""
    affordance_aliases = {
        "compact_position_actions_ms": "selfplay_max_projection_compact_position_actions_ms",
        "entity_rows_ms": "selfplay_max_projection_entity_rows_ms",
        "position_rows_ms": "selfplay_max_projection_position_rows_ms",
        "self_rows_ms": "selfplay_max_projection_self_rows_ms",
    }
    reduction_aliases = {
        "normalize_position_actions_ms": "selfplay_max_reduction_normalize_position_actions_ms",
        "known_tiles_ms": "selfplay_max_reduction_known_tiles_ms",
        "build_state_ms": "selfplay_max_reduction_build_state_ms",
    }
    for source_name, output_name in affordance_aliases.items():
        value = _max_trace_mapping_value(artifact, "affordance_timing", source_name)
        if value is not None:
            metrics[output_name] = value
    for source_name, output_name in reduction_aliases.items():
        value = _max_trace_mapping_value(artifact, "reduction_timing", source_name)
        if value is not None:
            metrics[output_name] = value

    server_total_values: list[float] = []
    server_phase_values: dict[str, list[float]] = {}
    for trace in artifact.result.traces:
        total_ms = trace.server_timing.get("total_ms")
        if isinstance(total_ms, (int, float)) and not isinstance(total_ms, bool):
            server_total_values.append(float(total_ms))
        phases = trace.server_timing.get("phases")
        if not isinstance(phases, dict):
            continue
        for phase_name, value in phases.items():
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                server_phase_values.setdefault(str(phase_name), []).append(float(value))
    if server_total_values:
        server_distribution = _distribution(server_total_values)
        _add_stage_metrics(metrics, "server_command_ms", server_distribution)
        metrics["max_server_command_ms"] = server_distribution.max_ms
        metrics["server_command_max_ms"] = server_distribution.max_ms
    for phase_name, values in sorted(server_phase_values.items()):
        metrics[f"server_phase_max_{_metric_token(phase_name)}"] = round(max(values), 3)

    _add_server_suffix_alias(metrics, server_phase_values, "execute.action_by_index_ms", "max_execute_action_by_index_ms")
    _add_server_contains_alias(metrics, server_phase_values, "get_available_actions_ms", "max_get_available_actions_ms")
    _add_server_contains_alias(metrics, server_phase_values, "collect_aoe_actions_ms", "max_available_actions_collect_aoe_ms")
    _add_server_contains_alias(metrics, server_phase_values, "collect_los_actions_ms", "max_available_actions_collect_los_ms")

    action_phase_values: dict[str, list[float]] = {}
    action_total_values: list[float] = []
    for trace in artifact.result.traces:
        action_timing = trace.action_server_timing
        total_ms = action_timing.get("total_ms")
        if isinstance(total_ms, (int, float)) and not isinstance(total_ms, bool):
            action_total_values.append(float(total_ms))
        phases = action_timing.get("phases")
        if not isinstance(phases, dict):
            continue
        for phase_name, value in phases.items():
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                action_phase_values.setdefault(str(phase_name), []).append(float(value))
    if action_total_values:
        _add_stage_metrics(
            metrics,
            "action_server_total_ms",
            _distribution(action_total_values),
        )
    for phase_name, values in sorted(action_phase_values.items()):
        metrics[f"action_phase_max_{_metric_token(phase_name)}"] = round(max(values), 3)


def _add_server_suffix_alias(
    metrics: dict[str, Any],
    phase_values: dict[str, list[float]],
    phase_name: str,
    output_name: str,
) -> None:
    """Add a dashboard alias for one exact server timing phase."""
    values = phase_values.get(phase_name)
    if values:
        metrics[output_name] = round(max(values), 3)


def _add_server_contains_alias(
    metrics: dict[str, Any],
    phase_values: dict[str, list[float]],
    suffix: str,
    output_name: str,
) -> None:
    """Add a dashboard alias from every phase ending in a shared suffix."""
    values = [
        value
        for phase_name, samples in phase_values.items()
        if phase_name.endswith(suffix)
        for value in samples
    ]
    if values:
        metrics[output_name] = round(max(values), 3)


def _max_trace_mapping_value(
    artifact: ValidationRunArtifact,
    mapping_name: str,
    key: str,
) -> Optional[float]:
    """Return the maximum numeric trace mapping value for one key."""
    values: list[float] = []
    for trace in artifact.result.traces:
        mapping = getattr(trace, mapping_name)
        value = mapping.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            values.append(float(value))
    return round(max(values), 3) if values else None


def _stage_stat(
    artifact: ValidationRunArtifact,
    stage_name: str,
    field_name: str,
) -> Optional[float]:
    """Return one optional distribution field from an artifact stage."""
    distribution = (
        artifact.performance.normal_stages.get(stage_name)
        or artifact.performance.stages.get(stage_name)
    )
    if distribution is None:
        return None
    return float(getattr(distribution, field_name))


def _latest_timestamp(base_value: object, artifact_values: list[str]) -> str:
    """Return the latest deterministic timestamp normalized to UTC."""
    candidates = [_parse_timestamp(value) for value in artifact_values]
    if isinstance(base_value, str):
        candidates.append(_parse_timestamp(base_value))
    if not candidates:
        return datetime.fromtimestamp(0, timezone.utc).isoformat()
    return max(candidates).astimezone(timezone.utc).isoformat()


def _parse_timestamp(value: str) -> datetime:
    """Parse an ISO timestamp and require timezone information."""
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError(f"Timestamp must include a timezone: {value}")
    return parsed


def _metric_token(value: str) -> str:
    """Normalize a semantic tag or timing phase for a JSON metric key."""
    return "_".join(
        token
        for token in "".join(character.lower() if character.isalnum() else " " for character in value).split()
        if token
    )


def main() -> None:
    """Project repository validation artifacts into dashboard statistics."""
    ai_directory = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--stats",
        type=Path,
        default=ai_directory / "AGENT_UX_ITERATION_STATS.json",
        help="Dashboard statistics JSON to update.",
    )
    parser.add_argument(
        "--artifacts",
        type=Path,
        default=ai_directory / "evidence" / "runs",
        help="Directory containing immutable autonomous-run artifacts.",
    )
    parser.add_argument(
        "--direct-codex-artifacts",
        type=Path,
        default=ai_directory / "evidence" / "direct_codex_runs",
        help="Directory containing immutable direct Codex artifacts.",
    )
    args = parser.parse_args()
    projected = write_projected_dashboard_stats(
        args.stats,
        args.artifacts,
        args.direct_codex_artifacts,
    )
    run_count = len(projected.get("runs", []))
    print(f"Projected {run_count} artifact-backed dashboard runs into {args.stats}")


if __name__ == "__main__":
    main()
