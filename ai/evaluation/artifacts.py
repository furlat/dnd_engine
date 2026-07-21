"""Durable typed artifacts for agent self-play and validation evidence."""

from __future__ import annotations

from datetime import datetime, timezone
import math
from pathlib import Path
from statistics import fmean, median
from typing import Literal, Optional
from uuid import uuid4

from pydantic import BaseModel, Field

from ai.evaluation.constants import REQUIRED_SUBJECTIVITY_VALIDATOR
from ai.policy.source import CONTROLLER_PROFILE, policy_source_snapshot
from ai.policy.definitions import PolicyGenerationIdentity
from ai.external_selfplay import ExternalSelfPlayResult, ExternalSelfPlayTrace


class PolicyIdentity(BaseModel):
    """Immutable identity of the policy used for a validation run."""

    name: str = Field(description="Stable policy name.")
    version: str = Field(description="Human-readable policy version.")
    source_path: str = Field(description="Source path captured by the policy snapshot.")
    source_paths: list[str] = Field(
        default_factory=list,
        description="Ordered source manifest paths; empty only for artifacts predating composite manifests.",
    )
    source_hash: str = Field(description="SHA-256 hash of the exact composite policy source.")


class ParticipantSummary(BaseModel):
    """Participant identity observed in raw self-play command traces."""

    uuid: str = Field(description="Actor UUID recorded by the run.")
    name: str = Field(description="Actor display name.")
    faction: Optional[str] = Field(default=None, description="Actor faction when known.")
    session_id: str = Field(description="Subjective session that controlled the actor.")
    controller_mode: str = Field(description="Controller mode used for this participant.")


class CommandSummary(BaseModel):
    """Command-result counts derived from raw traces."""

    total: int = Field(description="Total command traces.")
    accepted: int = Field(default=0, description="Accepted command count.")
    rejected: int = Field(default=0, description="Rejected command count.")
    stale: int = Field(default=0, description="Stale command count.")
    error: int = Field(default=0, description="Error command count.")
    missing_result: int = Field(default=0, description="Traces without a command result.")


class LatencyDistribution(BaseModel):
    """Compact distribution of one measured runtime stage."""

    count: int = Field(description="Number of non-null timing samples.")
    min_ms: float = Field(description="Minimum sample in milliseconds.")
    mean_ms: float = Field(description="Arithmetic mean in milliseconds.")
    median_ms: float = Field(description="Median sample in milliseconds.")
    p95_ms: float = Field(description="Nearest-rank 95th percentile in milliseconds.")
    max_ms: float = Field(description="Maximum sample in milliseconds.")


class PerformanceSummary(BaseModel):
    """Run and per-stage timing summary derived from raw command traces."""

    elapsed_ms: float = Field(description="Total self-play wall-clock duration.")
    stages: dict[str, LatencyDistribution] = Field(
        default_factory=dict,
        description="All-sample timing distributions retained for compatibility and audit.",
    )
    normal_stages: dict[str, LatencyDistribution] = Field(
        default_factory=dict,
        description="Timing distributions from commands without deep diagnostic probes.",
    )
    diagnostic_stages: dict[str, LatencyDistribution] = Field(
        default_factory=dict,
        description="Timing distributions from commands with deep diagnostic probes enabled.",
    )


class SubjectivityAudit(BaseModel):
    """Objective post-run validation of the controller's disclosure boundary."""

    status: Literal["not_run", "passed", "failed"] = Field(description="Subjectivity audit status.")
    validator: Optional[str] = Field(default=None, description="Validator implementation or version.")
    violations: list[str] = Field(default_factory=list, description="Detected disclosure violations.")


class ValidationRunArtifact(BaseModel):
    """Immutable raw and derived evidence for one external self-play run."""

    schema_version: Literal[1] = Field(default=1, description="Artifact schema version.")
    run_id: str = Field(description="Stable unique run identifier and artifact filename stem.")
    generated_at: str = Field(description="UTC timestamp when the artifact was built.")
    source_revision: Optional[str] = Field(default=None, description="Source revision or working-tree identity when known.")
    random_seed: Optional[int] = Field(default=None, description="Random seed used by the run when controlled.")
    arena_id: str = Field(description="Validation arena identifier.")
    controller_mode: str = Field(description="Controller composition used for the run.")
    controller_profile: str = Field(
        default=CONTROLLER_PROFILE,
        description="Stable shared controller profile actually used by the run.",
    )
    policy: PolicyIdentity = Field(description="Exact traditional policy identity.")
    policy_generations_by_faction: dict[str, PolicyGenerationIdentity] = Field(
        default_factory=dict,
        description="Executable generation assigned independently to each faction when versioned play is active.",
    )
    participants: list[ParticipantSummary] = Field(default_factory=list, description="Observed controlled participants.")
    command_summary: CommandSummary = Field(description="Derived command-result counts.")
    performance: PerformanceSummary = Field(description="Derived timing distributions.")
    subjectivity: SubjectivityAudit = Field(description="Post-run subjectivity audit result.")
    result: ExternalSelfPlayResult = Field(description="Complete raw typed self-play result and command traces.")


_TIMING_FIELDS = (
    "snapshot_ms",
    "materialize_ms",
    "frame_fetch_ms",
    "frame_apply_ms",
    "pre_command_sync_ms",
    "pre_command_frame_fetch_ms",
    "pre_command_frame_apply_ms",
    "followup_frame_fetch_ms",
    "followup_frame_apply_ms",
    "reduce_ms",
    "fact_ms",
    "policy_ms",
    "local_decision_ms",
    "command_http_ms",
    "command_followup_sync_ms",
    "command_submit_ms",
    "total_ms",
)


def build_external_selfplay_artifact(
    result: ExternalSelfPlayResult,
    *,
    run_id: Optional[str] = None,
    random_seed: Optional[int] = None,
    source_revision: Optional[str] = None,
    subjectivity: Optional[SubjectivityAudit] = None,
) -> ValidationRunArtifact:
    """Build immutable evidence from one completed external self-play result.

    Args:
        result: Complete typed result returned by the self-play runner.
        run_id: Optional caller-supplied run identifier.
        random_seed: Random seed used for the run, when controlled.
        source_revision: Revision or working-tree identity, when known.
        subjectivity: Optional objective post-run disclosure audit.

    Returns:
        Typed raw and derived run artifact ready for durable storage.
    """
    policy = policy_source_snapshot()
    generated_at = datetime.now(timezone.utc).isoformat()
    return ValidationRunArtifact(
        run_id=run_id or _new_run_id(result.arena_id, generated_at),
        generated_at=generated_at,
        source_revision=source_revision,
        random_seed=random_seed,
        arena_id=result.arena_id,
        controller_mode="traditional_external_vs_traditional_external",
        controller_profile=CONTROLLER_PROFILE,
        policy=PolicyIdentity(
            name=policy.policy_name,
            version=policy.policy_version,
            source_path=policy.source_path,
            source_paths=policy.source_paths,
            source_hash=policy.source_sha256,
        ),
        policy_generations_by_faction=result.policy_generations_by_faction,
        participants=_participants(result),
        command_summary=_command_summary(result),
        performance=_performance_summary(result),
        subjectivity=subjectivity or audit_external_selfplay_subjectivity(result),
        result=result,
    )


def audit_external_selfplay_subjectivity(
    result: ExternalSelfPlayResult,
) -> SubjectivityAudit:
    """Validate that decisions and legal rows reference subjective facts only."""
    violations: list[str] = []
    for trace in result.traces:
        prefix = f"command[{trace.command_index}] actor={trace.actor_uuid}"
        known_entity_uuids = set(trace.subjective_known_entity_uuids)
        known_object_uuids = set(trace.subjective_known_object_uuids)
        known_uuids = known_entity_uuids | known_object_uuids
        known_positions = (
            set(trace.subjective_known_entity_positions)
            | set(trace.subjective_known_object_positions)
            | set(trace.subjective_known_tile_positions)
            | set(trace.subjective_visible_cell_positions)
            | set(trace.subjective_seen_cell_positions)
        )
        authorized_entity_uuids = set(trace.audit_authorized_entity_uuids)
        authorized_object_uuids = set(trace.audit_authorized_object_uuids)
        authorized_uuids = authorized_entity_uuids | authorized_object_uuids
        authorized_positions = set(trace.audit_authorized_positions)
        legal_rows = set(trace.subjective_affordance_row_ids)

        for entity_uuid in known_entity_uuids - authorized_entity_uuids:
            violations.append(
                f"{prefix}: subjective world disclosed an independently unauthorized entity UUID: {entity_uuid}"
            )
        for object_uuid in known_object_uuids - authorized_object_uuids:
            violations.append(
                f"{prefix}: subjective world disclosed an independently unauthorized object UUID: {object_uuid}"
            )
        for position in known_positions - authorized_positions:
            violations.append(
                f"{prefix}: subjective world disclosed an independently unauthorized position: {position}"
            )

        if trace.command_type == "execute" and trace.row_id not in legal_rows:
            violations.append(f"{prefix}: selected row was not disclosed by the decision epoch: {trace.row_id}")
        for label, entity_uuid in (
            ("target", trace.target_uuid),
            ("reference", trace.reference_entity_uuid),
            ("routine_target", trace.routine_target_uuid),
        ):
            if entity_uuid is not None and entity_uuid not in known_uuids:
                violations.append(f"{prefix}: {label} UUID was not subjectively known: {entity_uuid}")
            if entity_uuid is not None and entity_uuid not in authorized_uuids:
                violations.append(f"{prefix}: {label} UUID lacked an independent perception grant: {entity_uuid}")
        for label, entity_uuids in (
            ("affected", trace.affected_entity_uuids),
            ("extra_target", trace.extra_target_uuids or []),
            ("affordance_target", trace.subjective_affordance_target_uuids),
        ):
            for entity_uuid in entity_uuids:
                if entity_uuid not in known_uuids:
                    violations.append(f"{prefix}: {label} UUID was not subjectively known: {entity_uuid}")
                if entity_uuid not in authorized_uuids:
                    violations.append(f"{prefix}: {label} UUID lacked an independent perception grant: {entity_uuid}")
        for label, position in (
            ("target", trace.target_position),
            ("reference", trace.reference_entity_position),
            ("routine_target", trace.routine_target_position),
        ):
            if position is not None and position not in known_positions:
                violations.append(f"{prefix}: {label} position was not subjectively known: {position}")
            if position is not None and position not in authorized_positions:
                violations.append(f"{prefix}: {label} position lacked an independent perception grant: {position}")
        for label, positions in (
            ("affected", trace.affected_entity_positions),
            ("extra_target", trace.extra_target_positions or []),
            ("affordance_target", trace.subjective_affordance_target_positions),
        ):
            for position in positions:
                if position not in known_positions:
                    violations.append(f"{prefix}: {label} position was not subjectively known: {position}")
                if position not in authorized_positions:
                    violations.append(f"{prefix}: {label} position lacked an independent perception grant: {position}")
        violations.extend(
            _audit_nested_policy_values(
                trace.policy_memory,
                prefix=f"{prefix}: policy_memory",
                authorized_uuids=authorized_uuids,
                authorized_positions=authorized_positions,
            )
        )
        for index, policy_step in enumerate(trace.policy_trace):
            violations.extend(
                _audit_nested_policy_values(
                    policy_step.model_dump(mode="json"),
                    prefix=f"{prefix}: policy_trace[{index}]",
                    authorized_uuids=authorized_uuids,
                    authorized_positions=authorized_positions,
                )
            )
    return SubjectivityAudit(
        status="failed" if violations else "passed",
        validator=REQUIRED_SUBJECTIVITY_VALIDATOR,
        violations=violations,
    )


def _audit_nested_policy_values(
    value: object,
    *,
    prefix: str,
    authorized_uuids: set[str],
    authorized_positions: set[tuple[int, int]],
    key: str = "",
) -> list[str]:
    """Audit UUID and position-bearing fields in derived policy telemetry."""
    violations: list[str] = []
    if isinstance(value, dict):
        for child_key, child_value in value.items():
            violations.extend(
                _audit_nested_policy_values(
                    child_value,
                    prefix=f"{prefix}.{child_key}",
                    authorized_uuids=authorized_uuids,
                    authorized_positions=authorized_positions,
                    key=str(child_key),
                )
            )
        return violations
    if isinstance(value, (list, tuple)):
        if _is_position_value(value) and (key.endswith("position") or key.endswith("positions")):
            position = (int(value[0]), int(value[1]))
            if position not in authorized_positions:
                violations.append(f"{prefix} lacked an independent perception grant: {position}")
            return violations
        for index, child_value in enumerate(value):
            violations.extend(
                _audit_nested_policy_values(
                    child_value,
                    prefix=f"{prefix}[{index}]",
                    authorized_uuids=authorized_uuids,
                    authorized_positions=authorized_positions,
                    key=key.removesuffix("s"),
                )
            )
        return violations
    if isinstance(value, str) and key.endswith("uuid") and value not in authorized_uuids:
        violations.append(f"{prefix} lacked an independent perception grant: {value}")
    return violations


def _is_position_value(value: list[object] | tuple[object, ...]) -> bool:
    """Return whether a JSON-like value is one integer grid position."""
    return (
        len(value) == 2
        and all(isinstance(component, int) and not isinstance(component, bool) for component in value)
    )


def write_validation_run_artifact(
    artifact: ValidationRunArtifact,
    output_directory: Path | str,
) -> Path:
    """Persist one immutable JSON run artifact without overwriting evidence.

    Args:
        artifact: Typed validation artifact to persist.
        output_directory: Directory that owns durable run JSON files.

    Returns:
        Path of the created artifact.

    Raises:
        FileExistsError: If the run id already has a persisted artifact.
    """
    directory = Path(output_directory)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{artifact.run_id}.json"
    with path.open("x", encoding="utf-8") as handle:
        handle.write(artifact.model_dump_json(indent=2))
        handle.write("\n")
    return path


def _participants(result: ExternalSelfPlayResult) -> list[ParticipantSummary]:
    """Derive stable participant rows from first subjective actor appearances."""
    by_uuid: dict[str, ParticipantSummary] = {}
    for trace in result.traces:
        by_uuid.setdefault(
            trace.actor_uuid,
            ParticipantSummary(
                uuid=trace.actor_uuid,
                name=trace.actor_name,
                faction=trace.actor_faction,
                session_id=trace.session_id,
                controller_mode="traditional_external",
            ),
        )
    return sorted(by_uuid.values(), key=lambda row: (row.faction or "", row.name, row.uuid))


def _command_summary(result: ExternalSelfPlayResult) -> CommandSummary:
    """Count command outcomes from raw traces."""
    counts = {"accepted": 0, "rejected": 0, "stale": 0, "error": 0, "missing_result": 0}
    for trace in result.traces:
        status = trace.command_status
        if status in {"accepted", "rejected", "stale", "error"}:
            counts[status] += 1
        else:
            counts["missing_result"] += 1
    return CommandSummary(total=len(result.traces), **counts)


def _performance_summary(result: ExternalSelfPlayResult) -> PerformanceSummary:
    """Derive per-stage timing distributions from raw traces."""
    normal_traces = [trace for trace in result.traces if not trace.deep_diagnostics_enabled]
    diagnostic_traces = [trace for trace in result.traces if trace.deep_diagnostics_enabled]
    return PerformanceSummary(
        elapsed_ms=result.elapsed_ms,
        stages=_trace_timing_distributions(result.traces),
        normal_stages=_trace_timing_distributions(normal_traces),
        diagnostic_stages=_trace_timing_distributions(diagnostic_traces),
    )


def _trace_timing_distributions(
    traces: list[ExternalSelfPlayTrace],
) -> dict[str, LatencyDistribution]:
    """Derive timing distributions for one instrumentation class."""
    stages: dict[str, LatencyDistribution] = {}
    for field_name in _TIMING_FIELDS:
        values = [
            float(value)
            for trace in traces
            if (value := getattr(trace, field_name)) is not None
        ]
        if values:
            stages[field_name] = _distribution(values)
    return stages


def _distribution(values: list[float]) -> LatencyDistribution:
    """Build a rounded nearest-rank latency distribution."""
    ordered = sorted(values)
    p95_index = max(0, math.ceil(0.95 * len(ordered)) - 1)
    return LatencyDistribution(
        count=len(ordered),
        min_ms=_round(ordered[0]),
        mean_ms=_round(fmean(ordered)),
        median_ms=_round(float(median(ordered))),
        p95_ms=_round(ordered[p95_index]),
        max_ms=_round(ordered[-1]),
    )


def _new_run_id(arena_id: str, generated_at: str) -> str:
    """Build a readable unique identifier safe for a JSON filename."""
    timestamp = generated_at.replace("-", "").replace(":", "").replace("+", "_").replace(".", "_")
    safe_arena = "".join(character if character.isalnum() or character in {"-", "_"} else "-" for character in arena_id)
    return f"{timestamp}-{safe_arena}-{uuid4().hex[:8]}"


def _round(value: float) -> float:
    """Round artifact timing values consistently."""
    return round(value, 3)
