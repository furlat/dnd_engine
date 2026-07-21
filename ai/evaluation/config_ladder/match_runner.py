"""Engine-bound worker adapter for one connected configuration match."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from ai.evaluation.arena_manifest import build_arena_manifest
from ai.evaluation.artifacts import (
    ValidationRunArtifact,
    build_external_selfplay_artifact,
)
from ai.evaluation.content_coverage import (
    MatchContentCoverageCollector,
    MatchContentCoverageEvidence,
)
from ai.evaluation.config_ladder.catalog_snapshot import (
    CatalogSnapshot,
    load_catalog_snapshot,
)
from ai.evaluation.config_ladder.contracts import ConnectedScheduleEntry, RatedOutcome
from ai.evaluation.config_ladder.normalization import (
    NormalizedMatchResult,
    normalize_selfplay_result,
)
from ai.evaluation.config_ladder.worker_contracts import (
    MatchWorkerRequest,
    WorkerStatus,
    WorkerTaskResult,
)
from ai.evaluation.constants import REQUIRED_SUBJECTIVITY_VALIDATOR
from ai.evaluation.elo_contract import ArenaManifest
from ai.evaluation.tournament import final_hp_by_faction, outcome_from_faction_hp
from ai.external_selfplay import ExternalSelfPlayResult, run_external_selfplay_with_arena_factory
from ai.policy.source import CONTROLLER_PROFILE, policy_source_snapshot
from dnd.scenarios.evaluation.assembler import assemble_composed_arena
from dnd.scenarios.evaluation.battlefield_catalog import get_battlefield
from dnd.scenarios.evaluation.combatant_catalog import get_combatant_configuration
from dnd.scenarios.evaluation.deployment_catalog import get_deployment
from dnd.scenarios.ai_validation_arenas import ValidationArena


class ScientificEligibility(BaseModel):
    """Scientific admission decision independent of worker process success."""

    model_config = ConfigDict(frozen=True)

    eligible: bool = Field(description="Whether this result may enter the strength model.")
    reasons: tuple[str, ...] = Field(description="Stable exclusion reasons when admission failed.")


class TerminationAdjudication(BaseModel):
    """Typed interpretation of the self-play runner's terminal boundary."""

    model_config = ConfigDict(frozen=True)

    kind: Literal["natural_end", "stalemate_draw", "unresolved"] = Field(
        description="Natural engine ending, finite-horizon stalemate, or unresolved run."
    )
    detail: str = Field(description="Exact publication rule applied to the runner status.")
    no_progress_command_window: int | None = Field(
        default=None,
        description="Consecutive accepted commands with an unchanged complete HP vector.",
    )


class RealMatchEvidence(BaseModel):
    """Complete authenticated evidence returned by one disposable match worker."""

    model_config = ConfigDict(frozen=True)

    schema_version: Literal[1] = Field(default=1, description="Real-match evidence schema version.")
    entry: ConnectedScheduleEntry = Field(description="Exact connected schedule row that was executed.")
    runtime_hashes: dict[str, str] = Field(description="Runtime identities independently observed by the worker.")
    arena_manifest: ArenaManifest = Field(description="Objective precombat measurement manifest.")
    run_artifact: ValidationRunArtifact = Field(description="Complete subjective self-play and audit artifact.")
    normalized_result: NormalizedMatchResult = Field(description="UUID- and timing-independent semantic result.")
    outcome: RatedOutcome | None = Field(description="Rated outcome, or null when outcome extraction failed.")
    faction_hp: dict[str, int] = Field(description="Final non-negative hit points summed by faction.")
    command_status_counts: dict[str, int] = Field(description="Command result counts derived from raw traces.")
    adjudication: TerminationAdjudication = Field(description="Typed terminal-boundary interpretation.")
    eligibility: ScientificEligibility = Field(description="Independent scientific admission result.")
    content_coverage: MatchContentCoverageEvidence = Field(
        default_factory=MatchContentCoverageEvidence,
        description="Evaluator-only rules-content lifecycle evidence for this match.",
    )


def run_connected_match(request: MatchWorkerRequest) -> WorkerTaskResult:
    """Execute one scheduled match through the subjective external-agent runtime.

    Args:
        request: Immutable worker request authenticated by the coordinator.

    Returns:
        A completed process result containing gameplay evidence and a separate
        scientific eligibility decision.

    Raises:
        ValueError: If any catalog, schedule, policy, or opening identity differs
            from the immutable request.
    """
    snapshot = _load_and_validate_snapshot(request)
    runtime_hashes = runtime_hashes_for_entry(request.entry, snapshot)
    _validate_entry_against_runtime_catalog(request.entry, snapshot)

    opening_faction = "heroes" if request.entry.opening_treatment == "hero_first" else "monsters"
    captured_manifests: list[ArenaManifest] = []
    content_collector = MatchContentCoverageCollector()

    def arena_factory() -> ValidationArena:
        return assemble_composed_arena(
            request.entry.hero_configuration_id,
            request.entry.monster_configuration_id,
            request.entry.battlefield_id,
            request.entry.deployment_id,
            opening_faction=opening_faction,
        )

    def capture_manifest(arena: ValidationArena) -> None:
        captured_manifests.append(build_arena_manifest(arena))
        content_collector.attach()

    try:
        result = run_external_selfplay_with_arena_factory(
            request.entry.match_id,
            arena_factory,
            max_commands=request.max_commands,
            random_seed=request.entry.simulation_seed,
            arena_observer=capture_manifest,
        )
    finally:
        content_collector.detach()
    if len(captured_manifests) != 1:
        raise ValueError("Real match did not capture exactly one precombat arena manifest.")
    manifest = captured_manifests[0]
    if manifest.opening_faction != opening_faction:
        raise ValueError(
            f"Opening treatment mismatch: expected {opening_faction}, observed {manifest.opening_faction}."
        )

    run_artifact = build_external_selfplay_artifact(
        result,
        run_id=request.entry.match_id,
        random_seed=request.entry.simulation_seed,
    )
    normalized = normalize_selfplay_result(result)
    faction_hp = final_hp_by_faction(result)
    adjudication = _termination_adjudication(result)
    raw_outcome = "draw" if adjudication.kind == "stalemate_draw" else outcome_from_faction_hp(faction_hp)
    outcome = _rated_outcome(raw_outcome)
    command_status_counts = _command_status_counts(run_artifact)
    eligibility = _scientific_eligibility(
        run_artifact,
        outcome=outcome,
        command_status_counts=command_status_counts,
        adjudication=adjudication,
    )
    evidence = RealMatchEvidence(
        entry=request.entry,
        runtime_hashes=runtime_hashes,
        arena_manifest=manifest,
        run_artifact=run_artifact,
        normalized_result=normalized,
        outcome=outcome,
        faction_hp=faction_hp,
        command_status_counts=command_status_counts,
        adjudication=adjudication,
        eligibility=eligibility,
        content_coverage=content_collector.build(),
    )
    return WorkerTaskResult(
        status=WorkerStatus.COMPLETED,
        payload=evidence.model_dump(mode="json"),
        manifest_hash=manifest.manifest_hash,
        normalized_result_hash=normalized.semantic_hash,
        subjectivity_status=run_artifact.subjectivity.status,
        subjectivity_violation_count=len(run_artifact.subjectivity.violations),
    )


def _load_and_validate_snapshot(request: MatchWorkerRequest) -> CatalogSnapshot:
    """Load the immutable catalog and authenticate its complete content hash."""
    if request.catalog_snapshot_path is None or request.catalog_snapshot_hash is None:
        raise ValueError("Real match requires an authenticated catalog snapshot.")
    snapshot_path = Path(request.catalog_snapshot_path)
    if not snapshot_path.is_absolute():
        raise ValueError("Catalog snapshot path must be absolute for isolated workers.")
    snapshot = load_catalog_snapshot(snapshot_path)
    if snapshot.catalog_hash != request.catalog_snapshot_hash:
        raise ValueError("Catalog snapshot content hash does not match the worker request.")
    return snapshot


def runtime_hashes_for_entry(entry: ConnectedScheduleEntry, snapshot: CatalogSnapshot) -> dict[str, str]:
    """Return identities observed from current source and immutable catalogs."""
    policy = policy_source_snapshot()
    return {
        "hero_configuration": entry.hero_configuration_hash,
        "monster_configuration": entry.monster_configuration_hash,
        "battlefield": entry.battlefield_hash,
        "deployment": entry.deployment_hash,
        "catalog_snapshot": snapshot.catalog_hash,
        "ruleset": snapshot.ruleset_id,
        "policy_version": policy.policy_version,
        "policy_source": policy.source_sha256,
        "controller_profile": CONTROLLER_PROFILE,
        "subjectivity_validator": REQUIRED_SUBJECTIVITY_VALIDATOR,
    }


def _validate_entry_against_runtime_catalog(
    entry: ConnectedScheduleEntry,
    snapshot: CatalogSnapshot,
) -> None:
    """Prove the scheduled row, snapshot, and imported builders are identical."""
    snapshot_values = {
        "hero_configuration": snapshot.hero(entry.hero_configuration_id).mechanical_hash,
        "monster_configuration": snapshot.monster_party(entry.monster_configuration_id).mechanical_hash,
        "battlefield": snapshot.battlefield(entry.battlefield_id).content_hash,
        "deployment": snapshot.deployment(entry.deployment_id).content_hash,
    }
    current_values = {
        "hero_configuration": get_combatant_configuration(entry.hero_configuration_id).mechanical_hash,
        "monster_configuration": get_combatant_configuration(entry.monster_configuration_id).mechanical_hash,
        "battlefield": get_battlefield(entry.battlefield_id).content_hash,
        "deployment": get_deployment(entry.deployment_id).content_hash,
    }
    expected_values = {
        "hero_configuration": entry.hero_configuration_hash,
        "monster_configuration": entry.monster_configuration_hash,
        "battlefield": entry.battlefield_hash,
        "deployment": entry.deployment_hash,
    }
    for label, expected in expected_values.items():
        if snapshot_values[label] != expected:
            raise ValueError(f"Snapshot {label} hash differs from the scheduled row.")
        if current_values[label] != expected:
            raise ValueError(f"Runtime {label} hash differs from the scheduled row.")


def _rated_outcome(raw_outcome: str) -> RatedOutcome | None:
    """Translate the existing faction outcome into the connected model contract."""
    if raw_outcome == "heroes":
        return RatedOutcome.HERO_WIN
    if raw_outcome == "monsters":
        return RatedOutcome.MONSTER_WIN
    if raw_outcome == "draw":
        return RatedOutcome.DRAW
    return None


def _termination_adjudication(result: ExternalSelfPlayResult) -> TerminationAdjudication:
    """Interpret runner completion without consulting hidden tactical state."""
    status = result.status
    if status == "encounter_ended":
        return TerminationAdjudication(
            kind="natural_end",
            detail="The authoritative encounter reached EncounterState.ENDED.",
        )
    if status == "stalemate_draw":
        evidence = result.stalemate_evidence
        if evidence is None:
            return TerminationAdjudication(
                kind="unresolved",
                detail="Runner reported a stalemate without finite-horizon evidence.",
            )
        return TerminationAdjudication(
            kind="stalemate_draw",
            detail=(
                f"The complete combatant HP vector remained unchanged across "
                f"{evidence.command_window} consecutive accepted commands."
            ),
            no_progress_command_window=evidence.command_window,
        )
    return TerminationAdjudication(
        kind="unresolved",
        detail=f"Runner stopped at unresolved status {status!r}.",
    )


def _command_status_counts(artifact: ValidationRunArtifact) -> dict[str, int]:
    """Return compact command counts from the typed artifact summary."""
    summary = artifact.command_summary
    return {
        key: value
        for key, value in {
            "accepted": summary.accepted,
            "rejected": summary.rejected,
            "stale": summary.stale,
            "error": summary.error,
            "missing_result": summary.missing_result,
        }.items()
        if value > 0
    }


def _scientific_eligibility(
    artifact: ValidationRunArtifact,
    *,
    outcome: RatedOutcome | None,
    command_status_counts: dict[str, int],
    adjudication: TerminationAdjudication,
) -> ScientificEligibility:
    """Apply gameplay, subjectivity, and protocol publication gates."""
    reasons: set[str] = set()
    if adjudication.kind == "unresolved":
        reasons.add(f"runner_status:{artifact.result.status}")
    if adjudication.kind == "natural_end" and artifact.result.final_state != "ended":
        reasons.add(f"encounter_state:{artifact.result.final_state}")
    if adjudication.kind == "stalemate_draw" and outcome != RatedOutcome.DRAW:
        reasons.add("stalemate_not_scored_as_draw")
    if artifact.subjectivity.status != "passed":
        reasons.add(f"subjectivity:{artifact.subjectivity.status}")
    if artifact.subjectivity.validator != REQUIRED_SUBJECTIVITY_VALIDATOR:
        reasons.add("subjectivity_validator_mismatch")
    if artifact.subjectivity.violations:
        reasons.add("subjectivity_violations")
    if outcome is None:
        reasons.add("unknown_outcome")
    for status, count in command_status_counts.items():
        if status != "accepted" and count > 0:
            reasons.add(f"command_status:{status}")
    return ScientificEligibility(eligible=not reasons, reasons=tuple(sorted(reasons)))
