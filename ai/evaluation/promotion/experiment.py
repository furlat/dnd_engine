"""Build, run, resume, and analyze versioned policy promotion experiments."""

from __future__ import annotations

import asyncio
from collections import Counter
import math
from pathlib import Path
from statistics import fmean
from typing import cast

from pydantic import Field

from ai.evaluation.config_ladder.artifact_store import read_gzip_json
from ai.evaluation.config_ladder.contracts import ConnectedRatingSchedule
from ai.evaluation.config_ladder.coordinator import run_isolated_coordinator
from ai.evaluation.config_ladder.worker_contracts import (
    AttemptOutcome,
    CoordinatorSummary,
    MatchWorkerRequest,
    PROMOTION_MATCH_ENTRYPOINT,
    RequestFactory,
    WorkerArtifactEnvelope,
    WorkerTaskMode,
)
from ai.evaluation.promotion.catalog import (
    TARGETED_POLICY_PROMOTION_BATTLEFIELD_IDS,
    build_default_promotion_matchups,
    build_symmetric_promotion_deployments,
    build_targeted_promotion_matchups,
)
from ai.evaluation.promotion.catalog_snapshot import (
    PromotionCatalogSnapshot,
    build_promotion_catalog_snapshot,
    write_promotion_catalog_snapshot,
)
from ai.evaluation.promotion.contracts import (
    PromotionObservation,
    PromotionSchedule,
    PromotionScheduleEntry,
)
from ai.evaluation.promotion.gates import (
    PromotionDecision,
    PromotionEvidenceGates,
    evaluate_promotion,
)
from ai.evaluation.promotion.match_runner import (
    PromotionMatchEvidence,
    promotion_runtime_hashes,
)
from ai.evaluation.promotion.model import PolicyPromotionResult, fit_policy_promotion
from ai.evaluation.promotion.parallelism import resolve_promotion_worker_count
from ai.evaluation.promotion.schedule import build_promotion_schedule
from ai.policy.generations import (
    BASELINE_GENERATION_ID,
    CANDIDATE_GENERATION_ID,
    get_policy_implementation,
)
from dnd.scenarios.evaluation.battlefield_catalog import BATTLEFIELDS
from dnd.scenarios.evaluation.combatant_catalog import list_combatant_configurations


class PromotionExperimentAnalysis(PromotionEvidenceGates):
    """Worker evidence counts plus the fitted model and promotion decision."""

    model: PolicyPromotionResult = Field(description="Joint roster-strength and policy-uplift fit.")
    decision: PromotionDecision = Field(description="Final auditable candidate acceptance decision.")
    matchup_counts: dict[str, int] = Field(description="Scheduled treatment rows by matchup family.")
    panel_counts: dict[str, int] = Field(description="Scheduled treatment rows by longitudinal panel.")
    total_commands: int = Field(ge=0, description="Commands across authenticated completed matches.")
    total_match_elapsed_ms: float = Field(ge=0.0, description="Sum of self-play wall durations.")
    mean_match_elapsed_ms: float = Field(ge=0.0, description="Mean self-play wall duration.")
    p95_match_elapsed_ms: float = Field(ge=0.0, description="Nearest-rank 95th percentile match duration.")
    max_active_workers: int = Field(ge=0, description="Observed coordinator parallelism high-water mark.")
    effected_handler_identities: int = Field(ge=0, description="Distinct handlers producing effects.")
    applied_condition_identities: int = Field(ge=0, description="Distinct applied condition identities.")
    consumed_item_identities: int = Field(ge=0, description="Distinct consumed item identities.")


def build_default_promotion_catalog(
    *,
    generated_at: str | None = None,
) -> PromotionCatalogSnapshot:
    """Build the full generic roster and symmetric-context catalog."""
    configurations = list_combatant_configurations()
    deployments = build_symmetric_promotion_deployments(BATTLEFIELDS)
    candidate = get_policy_implementation(CANDIDATE_GENERATION_ID).identity
    baseline = get_policy_implementation(BASELINE_GENERATION_ID).identity
    return build_promotion_catalog_snapshot(
        configurations=configurations,
        battlefields=BATTLEFIELDS,
        deployments=deployments,
        policy_generations=(baseline, candidate),
        generated_at=generated_at,
    )


def build_default_promotion_schedule(
    catalog: PromotionCatalogSnapshot,
    *,
    experiment_id: str,
    seeds: tuple[int, ...] = (20260718,),
    created_at: str | None = None,
) -> PromotionSchedule:
    """Build the sparse connected full-content promotion schedule."""
    candidate = catalog.policy(CANDIDATE_GENERATION_ID)
    baseline = catalog.policy(BASELINE_GENERATION_ID)
    return build_promotion_schedule(
        configurations=catalog.configurations,
        matchups=build_default_promotion_matchups(catalog.configurations),
        battlefields=catalog.battlefields,
        deployments=catalog.deployments,
        seeds=seeds,
        candidate=candidate,
        baseline=baseline,
        experiment_id=experiment_id,
        catalog_hash=catalog.catalog_hash,
        created_at=created_at,
    )


def build_targeted_promotion_schedule(
    catalog: PromotionCatalogSnapshot,
    *,
    experiment_id: str,
    seeds: tuple[int, ...] = (20260718, 20260719),
    created_at: str | None = None,
) -> PromotionSchedule:
    """Build the compact pathology-focused promotion schedule."""
    candidate = catalog.policy(CANDIDATE_GENERATION_ID)
    baseline = catalog.policy(BASELINE_GENERATION_ID)
    battlefields = tuple(
        battlefield
        for battlefield in catalog.battlefields
        if battlefield.battlefield_id in TARGETED_POLICY_PROMOTION_BATTLEFIELD_IDS
    )
    selected_ids = set(TARGETED_POLICY_PROMOTION_BATTLEFIELD_IDS)
    if {row.battlefield_id for row in battlefields} != selected_ids:
        missing = sorted(selected_ids - {row.battlefield_id for row in battlefields})
        raise ValueError(f"Targeted promotion battlefields missing from catalog: {missing}")
    return build_promotion_schedule(
        configurations=catalog.configurations,
        matchups=build_targeted_promotion_matchups(catalog.configurations),
        battlefields=battlefields,
        deployments=catalog.deployments,
        seeds=seeds,
        candidate=candidate,
        baseline=baseline,
        experiment_id=experiment_id,
        catalog_hash=catalog.catalog_hash,
        created_at=created_at,
    )


def build_promotion_request_factory(
    schedule: PromotionSchedule,
    catalog: PromotionCatalogSnapshot,
    catalog_path: Path,
    *,
    max_commands: int = 400,
    soft_timeout_seconds: float = 120.0,
) -> RequestFactory:
    """Bind immutable treatment rows to disposable real-match workers."""
    resolved_catalog_path = catalog_path.resolve()

    def request_factory(
        generic_entry: object,
        attempt_number: int,
        dispatch_id: str,
    ) -> MatchWorkerRequest:
        if not isinstance(generic_entry, PromotionScheduleEntry):
            raise ValueError("Promotion request factory received a non-promotion row.")
        entry = generic_entry
        return MatchWorkerRequest(
            experiment_id=schedule.experiment_id,
            schedule_hash=schedule.schedule_hash,
            catalog_hash=schedule.catalog_hash,
            entry=entry,
            attempt_number=attempt_number,
            dispatch_id=dispatch_id,
            mode=WorkerTaskMode.REAL_MATCH,
            max_commands=max_commands,
            soft_timeout_seconds=soft_timeout_seconds,
            expected_runtime_hashes=promotion_runtime_hashes(entry, catalog),
            catalog_snapshot_path=str(resolved_catalog_path),
            catalog_snapshot_hash=catalog.catalog_hash,
            real_match_entrypoint=PROMOTION_MATCH_ENTRYPOINT,
        )

    return cast(RequestFactory, request_factory)


async def run_promotion_experiment(
    schedule: PromotionSchedule,
    catalog: PromotionCatalogSnapshot,
    *,
    output_root: Path,
    spool_root: Path,
    worker_count: int | None = None,
    max_commands: int = 400,
    hard_timeout_seconds: float = 135.0,
    resume: bool = True,
) -> CoordinatorSummary:
    """Run or resume a promotion schedule through isolated worker processes."""
    experiment_dir = output_root.resolve() / schedule.experiment_id
    catalog_path = write_promotion_catalog_snapshot(catalog, experiment_dir / "catalog.json")
    request_factory = build_promotion_request_factory(
        schedule,
        catalog,
        catalog_path,
        max_commands=max_commands,
        soft_timeout_seconds=max(1.0, hard_timeout_seconds - 15.0),
    )
    coordinator_schedule = cast(ConnectedRatingSchedule, schedule)
    resolved_worker_count = resolve_promotion_worker_count(worker_count)
    return await run_isolated_coordinator(
        coordinator_schedule,
        output_root=output_root,
        spool_root=spool_root,
        request_factory=request_factory,
        worker_count=resolved_worker_count,
        hard_timeout_seconds=hard_timeout_seconds,
        resume=resume,
    )


def analyze_promotion_experiment(
    schedule: PromotionSchedule,
    summary: CoordinatorSummary,
    *,
    experiment_dir: Path,
    deterministic_mismatches: int = 0,
    content_coverage_regressions: int = 0,
) -> PromotionExperimentAnalysis:
    """Load authenticated artifacts, fit uplift, and apply promotion gates."""
    observations: list[PromotionObservation] = []
    infrastructure_failures = 0
    subjectivity_violations = 0
    protocol_failures = 0
    eligible_matches = 0
    command_count = 0
    elapsed_samples: list[float] = []
    effected_handlers: set[str] = set()
    applied_conditions: set[str] = set()
    consumed_items: set[str] = set()
    for record in summary.records:
        if record.outcome != AttemptOutcome.COMPLETED or record.artifact_path is None:
            infrastructure_failures += 1
            continue
        payload, _ = read_gzip_json(experiment_dir / record.artifact_path)
        envelope = WorkerArtifactEnvelope.model_validate(payload)
        evidence = PromotionMatchEvidence.model_validate(envelope.result.payload)
        command_count += evidence.run_artifact.command_summary.total
        elapsed_samples.append(evidence.run_artifact.performance.elapsed_ms)
        effected_handlers.update(evidence.content_coverage.handler_effect_counts)
        applied_conditions.update(evidence.content_coverage.condition_application_counts)
        consumed_items.update(evidence.content_coverage.item_consumption_counts)
        subjectivity_violations += len(evidence.run_artifact.subjectivity.violations)
        command_summary = evidence.run_artifact.command_summary
        protocol_failures += (
            command_summary.rejected
            + command_summary.stale
            + command_summary.error
            + command_summary.missing_result
        )
        if not evidence.eligibility.eligible or evidence.outcome is None:
            continue
        eligible_matches += 1
        entry = evidence.entry
        observations.append(PromotionObservation(
            match_id=entry.match_id,
            comparison_block_id=entry.comparison_block_id,
            side_a_configuration_id=entry.side_a_configuration_id,
            side_b_configuration_id=entry.side_b_configuration_id,
            side_a_policy_generation_id=entry.side_a_policy_generation_id,
            side_b_policy_generation_id=entry.side_b_policy_generation_id,
            candidate_generation_id=entry.candidate_generation_id,
            baseline_generation_id=entry.baseline_generation_id,
            battlefield_id=entry.battlefield_id,
            deployment_id=entry.deployment_id,
            opening_treatment=entry.opening_treatment,
            matchup_family=entry.matchup_family,
            panel=entry.panel,
            matchup_tags=entry.matchup_tags,
            outcome=evidence.outcome,
        ))
    model = fit_policy_promotion(observations)
    evidence_gates = PromotionEvidenceGates(
        scheduled_matches=len(schedule.entries),
        eligible_matches=eligible_matches,
        infrastructure_failures=infrastructure_failures,
        subjectivity_violations=subjectivity_violations,
        protocol_failures=protocol_failures,
        deterministic_mismatches=deterministic_mismatches,
        content_coverage_regressions=content_coverage_regressions,
    )
    decision = evaluate_promotion(model, evidence_gates)
    ordered_elapsed = sorted(elapsed_samples)
    p95_index = max(0, math.ceil(0.95 * len(ordered_elapsed)) - 1) if ordered_elapsed else 0
    return PromotionExperimentAnalysis(
        **evidence_gates.model_dump(),
        model=model,
        decision=decision,
        matchup_counts=dict(sorted(Counter(row.matchup_family.value for row in schedule.entries).items())),
        panel_counts=dict(sorted(Counter(row.panel.value for row in schedule.entries).items())),
        total_commands=command_count,
        total_match_elapsed_ms=sum(elapsed_samples),
        mean_match_elapsed_ms=fmean(elapsed_samples) if elapsed_samples else 0.0,
        p95_match_elapsed_ms=ordered_elapsed[p95_index] if ordered_elapsed else 0.0,
        max_active_workers=summary.max_active_workers,
        effected_handler_identities=len(effected_handlers),
        applied_condition_identities=len(applied_conditions),
        consumed_item_identities=len(consumed_items),
    )


def run_default_promotion_experiment(
    *,
    experiment_id: str,
    output_root: Path,
    spool_root: Path,
    worker_count: int | None = None,
) -> CoordinatorSummary:
    """Synchronous convenience entry point for the complete default loop."""
    catalog = build_default_promotion_catalog()
    schedule = build_default_promotion_schedule(catalog, experiment_id=experiment_id)
    return asyncio.run(run_promotion_experiment(
        schedule,
        catalog,
        output_root=output_root,
        spool_root=spool_root,
        worker_count=worker_count,
    ))
