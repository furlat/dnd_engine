from __future__ import annotations

import asyncio
from pathlib import Path

from ai.evaluation.config_ladder.artifact_store import read_gzip_json
from ai.evaluation.config_ladder.catalog_snapshot import (
    build_catalog_snapshot,
    write_catalog_snapshot,
)
from ai.evaluation.config_ladder.coordinator import run_isolated_coordinator
from ai.evaluation.config_ladder.experiment import (
    ExperimentExecution,
    build_experiment_report,
    load_retained_evidence,
    paired_strength_observations,
    write_experiment_report,
)
from ai.evaluation.config_ladder.match_runner import (
    RealMatchEvidence,
    runtime_hashes_for_entry,
)
from ai.evaluation.config_ladder.schedule import build_connected_schedule
from ai.evaluation.config_ladder.worker_contracts import (
    AttemptOutcome,
    MatchWorkerRequest,
    WorkerArtifactEnvelope,
    WorkerTaskMode,
)
from ai.policy.source import policy_source_snapshot
from dnd.scenarios.evaluation.battlefield_catalog import get_battlefield
from dnd.scenarios.evaluation.combatant_catalog import get_combatant_configuration
from dnd.scenarios.evaluation.deployment_catalog import get_deployment


def test_real_connected_match_runs_through_subjective_contract_in_isolated_processes(
    tmp_path: Path,
) -> None:
    policy = policy_source_snapshot()
    hero = get_combatant_configuration("hero.barbarian_l5_berserker_torch")
    monsters = get_combatant_configuration("monsters.berserker_duelist")
    battlefield = get_battlefield("battlefield.open_floor_bright")
    deployments = tuple(get_deployment(value) for value in battlefield.deployment_ids)
    snapshot = build_catalog_snapshot(
        heroes=(hero,),
        monster_parties=(monsters,),
        battlefields=(battlefield,),
        deployments=deployments,
        policy_version=policy.policy_version,
        policy_source_hash=policy.source_sha256,
        generated_at="2026-07-17T00:00:00+00:00",
    )
    snapshot_path = write_catalog_snapshot(snapshot, tmp_path / "catalog.json").resolve()
    schedule = build_connected_schedule(
        heroes=(hero,),
        monster_parties=(monsters,),
        battlefields=(battlefield,),
        deployments=deployments,
        seeds=(1701,),
        experiment_id="isolated-real-smoke",
        created_at="2026-07-17T00:00:00+00:00",
    )

    def request_factory(entry, attempt_number: int, dispatch_id: str) -> MatchWorkerRequest:
        return MatchWorkerRequest(
            experiment_id=schedule.experiment_id,
            schedule_hash=schedule.schedule_hash,
            catalog_hash=schedule.catalog_hash,
            entry=entry,
            attempt_number=attempt_number,
            dispatch_id=dispatch_id,
            mode=WorkerTaskMode.REAL_MATCH,
            max_commands=160,
            soft_timeout_seconds=45.0,
            expected_runtime_hashes=runtime_hashes_for_entry(entry, snapshot),
            catalog_snapshot_path=str(snapshot_path),
            catalog_snapshot_hash=snapshot.catalog_hash,
            real_match_entrypoint="ai.evaluation.config_ladder.match_runner:run_connected_match",
        )

    summary = asyncio.run(
        run_isolated_coordinator(
            schedule,
            output_root=tmp_path / "canonical",
            spool_root=tmp_path / "spool",
            request_factory=request_factory,
            worker_count=2,
            hard_timeout_seconds=60.0,
            max_infrastructure_attempts=1,
        )
    )

    assert len(summary.records) == 2
    assert all(record.outcome == AttemptOutcome.COMPLETED for record in summary.records)
    assert len({record.worker_pid for record in summary.records}) == 2
    experiment_dir = tmp_path / "canonical" / schedule.experiment_id
    for record in summary.records:
        assert record.artifact_path is not None
        artifact_value, _ = read_gzip_json(experiment_dir / record.artifact_path)
        envelope = WorkerArtifactEnvelope.model_validate(artifact_value)
        evidence = RealMatchEvidence.model_validate(envelope.result.payload)
        assert evidence.entry == record.entry
        assert evidence.run_artifact.subjectivity.status == "passed"
        assert evidence.run_artifact.subjectivity.violations == []
        assert evidence.normalized_result.semantic_hash == record.normalized_result_hash
        assert evidence.arena_manifest.opening_faction == (
            "heroes" if record.entry.opening_treatment == "hero_first" else "monsters"
        )
        assert evidence.outcome is not None
        assert evidence.eligibility.eligible
        assert evidence.content_coverage.event_lifecycle_counts
        assert evidence.content_coverage.handler_opportunity_counts

    execution = ExperimentExecution(
        summary=summary,
        experiment_dir=experiment_dir,
        wall_seconds=1.0,
    )
    retained = load_retained_evidence(execution)
    assert retained.content_coverage.lifecycle_evidence_match_count == 2
    assert retained.content_coverage.affordance_evidence_match_count == 2
    observations, excluded_pairs = paired_strength_observations(schedule, retained)
    assert len(observations) == 2
    assert excluded_pairs == {}
    report = build_experiment_report(
        schedule,
        snapshot,
        execution,
        retained,
        bootstrap_replicates=10,
    )
    json_path, html_path = write_experiment_report(report, experiment_dir=experiment_dir)
    assert json_path.is_file()
    assert html_path.is_file()
    assert "Who Was Powerful" in html_path.read_text(encoding="utf-8")
