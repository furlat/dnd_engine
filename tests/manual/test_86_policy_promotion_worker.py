"""Real and isolated-worker checks for versioned policy promotion."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import cast

from ai.evaluation.config_ladder.coordinator import run_isolated_coordinator
from ai.evaluation.config_ladder.contracts import ConnectedRatingSchedule
from ai.evaluation.config_ladder.worker_contracts import (
    AttemptOutcome,
    MatchWorkerRequest,
    ProbeOperation,
    ProbeTask,
    WorkerTaskMode,
)
from ai.evaluation.promotion import (
    MatchupFamily,
    PromotionMatchupSpec,
    PromotionPanel,
    build_promotion_schedule,
    build_symmetric_promotion_deployments,
)
from ai.evaluation.promotion.catalog_snapshot import (
    build_promotion_catalog_snapshot,
    write_promotion_catalog_snapshot,
)
from ai.evaluation.promotion.contracts import PromotionScheduleEntry
from ai.evaluation.promotion.match_runner import PromotionMatchEvidence, run_promotion_match
from ai.evaluation.promotion.experiment import (
    analyze_promotion_experiment,
    build_promotion_request_factory,
)
from ai.evaluation.config_ladder.artifact_store import read_gzip_json
from ai.evaluation.config_ladder.worker_contracts import WorkerArtifactEnvelope
from ai.policy.generations import (
    BASELINE_GENERATION_ID,
    CANDIDATE_GENERATION_ID,
    get_policy_implementation,
)
from dnd.scenarios.evaluation.battlefield_catalog import get_battlefield
from dnd.scenarios.evaluation.combatant_catalog import get_combatant_configuration


def test_real_monster_duel_attributes_each_faction_to_its_policy_generation(tmp_path: Path) -> None:
    """One real treatment preserves subjectivity and independent policy provenance."""
    schedule, catalog, catalog_path = _small_promotion_fixture(tmp_path)
    entry = schedule.entries[0]
    request = MatchWorkerRequest(
        experiment_id=schedule.experiment_id,
        schedule_hash=schedule.schedule_hash,
        catalog_hash=schedule.catalog_hash,
        entry=entry,
        attempt_number=1,
        dispatch_id="direct-real-promotion",
        mode=WorkerTaskMode.REAL_MATCH,
        max_commands=220,
        soft_timeout_seconds=60.0,
        expected_runtime_hashes={},
        catalog_snapshot_path=str(catalog_path),
        catalog_snapshot_hash=catalog.catalog_hash,
        real_match_entrypoint="ai.evaluation.promotion.match_runner:run_promotion_match",
    )

    result = run_promotion_match(request)
    evidence = PromotionMatchEvidence.model_validate(result.payload)

    assert evidence.outcome is not None
    assert evidence.eligibility.eligible
    assert evidence.run_artifact.subjectivity.status == "passed"
    assert evidence.run_artifact.subjectivity.violations == []
    assert set(evidence.run_artifact.policy_generations_by_faction) == {"side_a", "side_b"}
    assert evidence.run_artifact.policy_generations_by_faction["side_a"].generation_id == entry.side_a_policy_generation_id
    assert evidence.run_artifact.policy_generations_by_faction["side_b"].generation_id == entry.side_b_policy_generation_id
    assert {trace.policy_generation_id for trace in evidence.run_artifact.result.traces} == {
        entry.side_a_policy_generation_id,
        entry.side_b_policy_generation_id,
    }


def test_promotion_rows_parallelize_and_resume_through_existing_isolated_coordinator(tmp_path: Path) -> None:
    """Promotion contracts retain process isolation, canonical order, and resume."""
    schedule, _, _ = _small_promotion_fixture(tmp_path)

    def request_factory(entry, attempt_number: int, dispatch_id: str) -> MatchWorkerRequest:
        assert isinstance(entry, PromotionScheduleEntry)
        return MatchWorkerRequest(
            experiment_id=schedule.experiment_id,
            schedule_hash=schedule.schedule_hash,
            catalog_hash=schedule.catalog_hash,
            entry=entry,
            attempt_number=attempt_number,
            dispatch_id=dispatch_id,
            mode=WorkerTaskMode.PROBE,
            probe=ProbeTask(operation=ProbeOperation.ECHO, payload={"match_id": entry.match_id}),
        )

    coordinator_schedule = cast(ConnectedRatingSchedule, schedule)
    first = asyncio.run(run_isolated_coordinator(
        coordinator_schedule,
        output_root=tmp_path / "canonical",
        spool_root=tmp_path / "spool",
        request_factory=request_factory,
        worker_count=2,
        hard_timeout_seconds=20.0,
        max_infrastructure_attempts=1,
    ))
    second = asyncio.run(run_isolated_coordinator(
        coordinator_schedule,
        output_root=tmp_path / "canonical",
        spool_root=tmp_path / "spool",
        request_factory=request_factory,
        worker_count=2,
        hard_timeout_seconds=20.0,
        max_infrastructure_attempts=1,
    ))

    assert len(first.records) == 4
    assert all(row.outcome == AttemptOutcome.COMPLETED for row in first.records)
    assert len({row.worker_pid for row in first.records}) == 4
    assert first.max_active_workers == 2
    assert second.spawned_worker_count == 0
    assert second.resumed_record_count == 4


def test_complete_real_block_is_assignment_balanced_for_distinct_generations(tmp_path: Path) -> None:
    """A real four-row block preserves both assignments for distinct policies."""
    schedule, catalog, catalog_path = _small_promotion_fixture(tmp_path)
    request_factory = build_promotion_request_factory(
        schedule,
        catalog,
        catalog_path,
        max_commands=220,
        soft_timeout_seconds=60.0,
    )
    coordinator_schedule = cast(ConnectedRatingSchedule, schedule)
    summary = asyncio.run(run_isolated_coordinator(
        coordinator_schedule,
        output_root=tmp_path / "real-canonical",
        spool_root=tmp_path / "real-spool",
        request_factory=request_factory,
        worker_count=2,
        hard_timeout_seconds=75.0,
        max_infrastructure_attempts=1,
    ))
    experiment_dir = tmp_path / "real-canonical" / schedule.experiment_id
    by_treatment: dict[tuple[str, str], PromotionMatchEvidence] = {}
    for record in summary.records:
        assert record.outcome == AttemptOutcome.COMPLETED
        assert record.artifact_path is not None
        value, _ = read_gzip_json(experiment_dir / record.artifact_path)
        envelope = WorkerArtifactEnvelope.model_validate(value)
        evidence = PromotionMatchEvidence.model_validate(envelope.result.payload)
        assert evidence.eligibility.eligible
        by_treatment[(evidence.entry.opening_treatment, evidence.entry.policy_assignment)] = evidence

    assert len(by_treatment) == 4
    for opening in ("side_a_first", "side_b_first"):
        candidate_a = by_treatment[(opening, "candidate_a")].normalized_result
        candidate_b = by_treatment[(opening, "candidate_b")].normalized_result
        assert candidate_a.command_count > 0
        assert candidate_b.command_count > 0
        assert candidate_a.semantic_hash != candidate_b.semantic_hash
    analysis = analyze_promotion_experiment(
        schedule,
        summary,
        experiment_dir=experiment_dir,
    )
    assert analysis.model.global_uplift.candidate_generation_id == CANDIDATE_GENERATION_ID
    assert analysis.model.global_uplift.baseline_generation_id == BASELINE_GENERATION_ID
    assert not analysis.decision.accepted
    assert analysis.decision.reasons


def _small_promotion_fixture(tmp_path: Path):
    """Build one four-treatment monster-versus-monster promotion block."""
    side_a = get_combatant_configuration("monsters.berserker_duelist")
    side_b = get_combatant_configuration("monsters.srd_brute_pair")
    battlefield = get_battlefield("battlefield.open_floor_bright")
    deployments = build_symmetric_promotion_deployments((battlefield,))
    candidate = get_policy_implementation(CANDIDATE_GENERATION_ID).identity
    baseline = get_policy_implementation(BASELINE_GENERATION_ID).identity
    catalog = build_promotion_catalog_snapshot(
        configurations=(side_a, side_b),
        battlefields=(battlefield,),
        deployments=deployments,
        policy_generations=(baseline, candidate),
        generated_at="2026-07-18T00:00:00+00:00",
    )
    schedule = build_promotion_schedule(
        configurations=catalog.configurations,
        matchups=(PromotionMatchupSpec(
            matchup_id="monster-duel",
            side_a_configuration_id=side_a.configuration_id,
            side_b_configuration_id=side_b.configuration_id,
            family=MatchupFamily.MONSTER_VS_MONSTER,
            panel=PromotionPanel.EXPANDED,
            tags=("monster-vs-monster", "melee"),
        ),),
        battlefields=catalog.battlefields,
        deployments=catalog.deployments,
        seeds=(8601,),
        candidate=candidate,
        baseline=baseline,
        experiment_id="promotion-worker-test",
        catalog_hash=catalog.catalog_hash,
        created_at="2026-07-18T00:00:00+00:00",
    )
    catalog_path = write_promotion_catalog_snapshot(catalog, tmp_path / "promotion-catalog.json").resolve()
    return schedule, catalog, catalog_path
