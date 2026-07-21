"""Isolated engine-bound worker for one policy promotion treatment."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from ai.evaluation.arena_manifest import build_arena_manifest
from ai.evaluation.artifacts import ValidationRunArtifact, build_external_selfplay_artifact
from ai.evaluation.config_ladder.match_runner import ScientificEligibility, TerminationAdjudication
from ai.evaluation.config_ladder.normalization import NormalizedMatchResult, normalize_selfplay_result
from ai.evaluation.config_ladder.worker_contracts import (
    MatchWorkerRequest,
    WorkerStatus,
    WorkerTaskResult,
)
from ai.evaluation.constants import REQUIRED_SUBJECTIVITY_VALIDATOR
from ai.evaluation.content_coverage import MatchContentCoverageCollector, MatchContentCoverageEvidence
from ai.evaluation.elo_contract import ArenaManifest
from ai.evaluation.promotion.catalog_snapshot import (
    PromotionCatalogSnapshot,
    load_promotion_catalog_snapshot,
)
from ai.evaluation.promotion.contracts import PromotionOutcome, PromotionScheduleEntry
from ai.external_selfplay import ExternalSelfPlayResult, run_external_selfplay_with_arena_factory
from ai.policy.generations import get_policy_implementation
from dnd.scenarios.ai_validation_arenas import ValidationArena
from dnd.scenarios.evaluation.assembler import assemble_generic_side_duel


class PromotionMatchEvidence(BaseModel):
    """Authenticated result of one counterbalanced policy treatment."""

    model_config = ConfigDict(frozen=True)

    schema_version: Literal[1] = Field(default=1, description="Promotion evidence schema version.")
    entry: PromotionScheduleEntry = Field(description="Exact treatment row executed by this worker.")
    runtime_hashes: dict[str, str] = Field(description="Runtime identities independently observed by the worker.")
    arena_manifest: ArenaManifest = Field(description="Objective precombat measurement manifest.")
    run_artifact: ValidationRunArtifact = Field(description="Complete subjective self-play evidence.")
    normalized_result: NormalizedMatchResult = Field(description="UUID-independent semantic outcome.")
    outcome: PromotionOutcome | None = Field(description="Rated side-A outcome when adjudicable.")
    faction_hp: dict[str, int] = Field(description="Final non-negative HP by neutral faction.")
    adjudication: TerminationAdjudication = Field(description="Natural, stalemate, or unresolved boundary.")
    eligibility: ScientificEligibility = Field(description="Scientific admission independent of worker success.")
    content_coverage: MatchContentCoverageEvidence = Field(description="Rules-content lifecycle evidence.")


def run_promotion_match(request: MatchWorkerRequest) -> WorkerTaskResult:
    """Execute one generic-side treatment under independently versioned policies."""
    if not isinstance(request.entry, PromotionScheduleEntry):
        raise ValueError("Promotion worker received a non-promotion schedule entry.")
    entry = request.entry
    snapshot = _load_snapshot(request)
    _validate_runtime(entry, snapshot)
    side_a_policy = get_policy_implementation(entry.side_a_policy_generation_id)
    side_b_policy = get_policy_implementation(entry.side_b_policy_generation_id)
    deployment = snapshot.deployment(entry.deployment_id)
    captured_manifests: list[ArenaManifest] = []
    collector = MatchContentCoverageCollector()

    def arena_factory() -> ValidationArena:
        return assemble_generic_side_duel(
            entry.side_a_configuration_id,
            entry.side_b_configuration_id,
            entry.battlefield_id,
            side_a_slots=deployment.hero_slots,
            side_b_slots=deployment.monster_slots,
            opening_faction=("side_a" if entry.opening_treatment == "side_a_first" else "side_b"),
        )

    def capture(arena: ValidationArena) -> None:
        captured_manifests.append(build_arena_manifest(arena))
        collector.attach()

    try:
        result = run_external_selfplay_with_arena_factory(
            entry.match_id,
            arena_factory,
            max_commands=request.max_commands,
            random_seed=entry.simulation_seed,
            arena_observer=capture,
            policy_implementations_by_faction={
                "side_a": side_a_policy,
                "side_b": side_b_policy,
            },
        )
    finally:
        collector.detach()
    if len(captured_manifests) != 1:
        raise ValueError("Promotion match did not capture exactly one arena manifest.")
    artifact = build_external_selfplay_artifact(
        result,
        run_id=entry.match_id,
        random_seed=entry.simulation_seed,
    )
    normalized = normalize_selfplay_result(result)
    faction_hp = _final_hp_by_faction(result)
    adjudication = _adjudication(result)
    outcome = _promotion_outcome(faction_hp, adjudication)
    eligibility = _eligibility(artifact, outcome, adjudication)
    runtime_hashes = promotion_runtime_hashes(entry, snapshot)
    evidence = PromotionMatchEvidence(
        entry=entry,
        runtime_hashes=runtime_hashes,
        arena_manifest=captured_manifests[0],
        run_artifact=artifact,
        normalized_result=normalized,
        outcome=outcome,
        faction_hp=faction_hp,
        adjudication=adjudication,
        eligibility=eligibility,
        content_coverage=collector.build(),
    )
    return WorkerTaskResult(
        status=WorkerStatus.COMPLETED,
        payload=evidence.model_dump(mode="json"),
        manifest_hash=evidence.arena_manifest.manifest_hash,
        normalized_result_hash=normalized.semantic_hash,
        subjectivity_status=artifact.subjectivity.status,
        subjectivity_violation_count=len(artifact.subjectivity.violations),
    )


def promotion_runtime_hashes(
    entry: PromotionScheduleEntry,
    snapshot: PromotionCatalogSnapshot,
) -> dict[str, str]:
    """Return all runtime identities authenticated by an isolated worker."""
    return {
        "side_a_configuration": entry.side_a_configuration_hash,
        "side_b_configuration": entry.side_b_configuration_hash,
        "battlefield": entry.battlefield_hash,
        "deployment": entry.deployment_hash,
        "side_a_policy": entry.side_a_policy_executable_hash,
        "side_b_policy": entry.side_b_policy_executable_hash,
        "catalog_snapshot": snapshot.catalog_hash,
        "ruleset": snapshot.ruleset_id,
        "subjectivity_validator": REQUIRED_SUBJECTIVITY_VALIDATOR,
    }


def _load_snapshot(request: MatchWorkerRequest) -> PromotionCatalogSnapshot:
    """Load and authenticate the immutable worker catalog."""
    if request.catalog_snapshot_path is None or request.catalog_snapshot_hash is None:
        raise ValueError("Promotion worker requires an authenticated catalog snapshot.")
    path = Path(request.catalog_snapshot_path)
    if not path.is_absolute():
        raise ValueError("Promotion catalog path must be absolute.")
    snapshot = load_promotion_catalog_snapshot(path)
    if snapshot.catalog_hash != request.catalog_snapshot_hash:
        raise ValueError("Promotion catalog hash differs from the worker request.")
    return snapshot


def _validate_runtime(entry: PromotionScheduleEntry, snapshot: PromotionCatalogSnapshot) -> None:
    """Prove scheduled identities match catalogs and executable registry."""
    expected = {
        "side_a_configuration": entry.side_a_configuration_hash,
        "side_b_configuration": entry.side_b_configuration_hash,
        "battlefield": entry.battlefield_hash,
        "deployment": entry.deployment_hash,
        "side_a_policy": entry.side_a_policy_executable_hash,
        "side_b_policy": entry.side_b_policy_executable_hash,
    }
    observed = {
        "side_a_configuration": snapshot.configuration(entry.side_a_configuration_id).mechanical_hash,
        "side_b_configuration": snapshot.configuration(entry.side_b_configuration_id).mechanical_hash,
        "battlefield": snapshot.battlefield(entry.battlefield_id).content_hash,
        "deployment": snapshot.deployment(entry.deployment_id).content_hash,
        "side_a_policy": get_policy_implementation(entry.side_a_policy_generation_id).identity.executable_sha256,
        "side_b_policy": get_policy_implementation(entry.side_b_policy_generation_id).identity.executable_sha256,
    }
    for label, value in expected.items():
        if observed[label] != value:
            raise ValueError(f"Promotion runtime {label} identity differs from the schedule.")
        generation_id = (
            entry.side_a_policy_generation_id if label == "side_a_policy" else entry.side_b_policy_generation_id
        )
        if label.endswith("policy") and snapshot.policy(generation_id).executable_sha256 != value:
            raise ValueError(f"Promotion snapshot {label} identity differs from the schedule.")


def _final_hp_by_faction(result: ExternalSelfPlayResult) -> dict[str, int]:
    """Aggregate final actor HP under neutral runtime factions."""
    totals: dict[str, int] = {}
    for actor_name, hp in result.final_hp_by_actor.items():
        faction = result.final_faction_by_actor.get(actor_name)
        if faction is not None:
            totals[faction] = totals.get(faction, 0) + max(0, hp)
    return totals


def _adjudication(result: ExternalSelfPlayResult) -> TerminationAdjudication:
    """Interpret the runner boundary without exposing objective state to policies."""
    if result.status == "encounter_ended":
        return TerminationAdjudication(kind="natural_end", detail="Encounter reached its authoritative end state.")
    if result.status == "stalemate_draw" and result.stalemate_evidence is not None:
        return TerminationAdjudication(
            kind="stalemate_draw",
            detail="Complete combatant HP remained unchanged across the finite-horizon window.",
            no_progress_command_window=result.stalemate_evidence.command_window,
        )
    return TerminationAdjudication(kind="unresolved", detail=f"Runner stopped at {result.status!r}.")


def _promotion_outcome(
    faction_hp: dict[str, int],
    adjudication: TerminationAdjudication,
) -> PromotionOutcome | None:
    """Resolve side-A win, side-B win, draw, or an unrateable boundary."""
    if adjudication.kind == "stalemate_draw":
        return PromotionOutcome.DRAW
    if adjudication.kind != "natural_end":
        return None
    side_a_hp = faction_hp.get("side_a", 0)
    side_b_hp = faction_hp.get("side_b", 0)
    if side_a_hp > 0 and side_b_hp <= 0:
        return PromotionOutcome.SIDE_A_WIN
    if side_b_hp > 0 and side_a_hp <= 0:
        return PromotionOutcome.SIDE_B_WIN
    if side_a_hp == side_b_hp:
        return PromotionOutcome.DRAW
    return PromotionOutcome.SIDE_A_WIN if side_a_hp > side_b_hp else PromotionOutcome.SIDE_B_WIN


def _eligibility(
    artifact: ValidationRunArtifact,
    outcome: PromotionOutcome | None,
    adjudication: TerminationAdjudication,
) -> ScientificEligibility:
    """Apply protocol, subjectivity, terminal, and policy-attribution gates."""
    reasons: set[str] = set()
    if outcome is None:
        reasons.add("unknown_outcome")
    if adjudication.kind == "unresolved":
        reasons.add(f"runner_status:{artifact.result.status}")
    if artifact.subjectivity.status != "passed" or artifact.subjectivity.violations:
        reasons.add("subjectivity_failed")
    if set(artifact.policy_generations_by_faction) != {"side_a", "side_b"}:
        reasons.add("policy_assignment_missing")
    summary = artifact.command_summary
    if summary.rejected or summary.stale or summary.error or summary.missing_result:
        reasons.add("nonaccepted_command_result")
    return ScientificEligibility(eligible=not reasons, reasons=tuple(sorted(reasons)))
