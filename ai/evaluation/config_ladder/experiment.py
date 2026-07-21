"""End-to-end connected configuration experiment orchestration and analysis."""

from __future__ import annotations

import asyncio
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from hashlib import sha256
import json
import math
from pathlib import Path
from statistics import fmean
import time
from typing import Iterable

from pydantic import BaseModel, ConfigDict, Field

from ai.evaluation.config_ladder.artifact_store import (
    atomic_write_json,
    read_gzip_json,
    read_json_model,
)
from ai.evaluation.config_ladder.catalog_snapshot import (
    CatalogSnapshot,
    build_catalog_snapshot,
)
from ai.evaluation.config_ladder.contracts import (
    ConnectedRatingSchedule,
    ConnectedScheduleEntry,
    RatedOutcome,
    StrengthObservation,
)
from ai.evaluation.config_ladder.coordinator import run_isolated_coordinator
from ai.evaluation.config_ladder.match_runner import (
    ScientificEligibility,
    TerminationAdjudication,
    runtime_hashes_for_entry,
)
from ai.evaluation.config_ladder.online_elo import (
    audit_elo_order_sensitivity,
    build_provisional_paired_elo,
)
from ai.evaluation.config_ladder.report_projection import build_report_projection
from ai.evaluation.config_ladder.report_renderer import write_report_html
from ai.evaluation.config_ladder.scaling import (
    ParallelScalingAnalysis,
    ScalingPilot,
    analyze_parallel_scaling,
)
from ai.evaluation.config_ladder.schedule import (
    build_connected_schedule,
    schedule_connectivity,
)
from ai.evaluation.config_ladder.strength_model import fit_configuration_strength
from ai.evaluation.config_ladder.uncertainty import bootstrap_configuration_strength
from ai.evaluation.content_catalog import build_implemented_content_catalog
from ai.evaluation.config_ladder.worker_contracts import (
    AttemptOutcome,
    AttemptReceipt,
    CoordinatorSummary,
    DEFAULT_RATING_MAX_COMMANDS,
    MatchWorkerRequest,
    MatchWorkerResponse,
    RequestFactory,
    WorkerTaskMode,
)
from ai.policy.source import policy_source_snapshot
from dnd.scenarios.evaluation.battlefield_catalog import BATTLEFIELDS
from dnd.scenarios.evaluation.combatant_catalog import (
    HERO_CONFIGURATIONS,
    MONSTER_PARTY_CONFIGURATIONS,
)
from dnd.scenarios.evaluation.deployment_catalog import DEPLOYMENTS
from dnd.spells import (
    ALL_SPELLS,
    CANTRIPS,
    LEVEL_1_SPELLS,
    LEVEL_2_SPELLS,
    LEVEL_3_SPELLS,
    LEVEL_4_SPELLS,
    LEVEL_5_SPELLS,
    LEVEL_6_SPELLS,
    LEVEL_7_SPELLS,
    LEVEL_8_SPELLS,
    LEVEL_9_SPELLS,
)


REAL_MATCH_ENTRYPOINT = "ai.evaluation.config_ladder.match_runner:run_connected_match"
_SPELLS_BY_LEVEL = (
    (0, CANTRIPS),
    (1, LEVEL_1_SPELLS),
    (2, LEVEL_2_SPELLS),
    (3, LEVEL_3_SPELLS),
    (4, LEVEL_4_SPELLS),
    (5, LEVEL_5_SPELLS),
    (6, LEVEL_6_SPELLS),
    (7, LEVEL_7_SPELLS),
    (8, LEVEL_8_SPELLS),
    (9, LEVEL_9_SPELLS),
)
_ITEM_SPELL_NAMES_BY_DISPLAY = {
    "Scroll of Fireball": ("Fireball",),
    "Scroll of Hold Person": ("Hold Person",),
    "Scroll of Magic Missile": ("Magic Missile",),
    "Scroll of Spike Growth": ("Spike Growth",),
    "Wand of Fire": ("Burning Hands", "Fireball"),
    "Wand of Magic Missiles": ("Magic Missile",),
}


@dataclass(frozen=True)
class ExperimentExecution:
    """One coordinator execution plus directly measured wall duration."""

    summary: CoordinatorSummary
    experiment_dir: Path
    wall_seconds: float


class RetainedMatchAnalysis(BaseModel):
    """Compact authenticated projection used by aggregate analysis.

    Complete event, command, and perception evidence remains in the immutable
    compressed worker artifact. Aggregate rating and performance analysis only
    retains the fields it actually consumes so thousands of full event histories
    do not remain materialized in memory.
    """

    model_config = ConfigDict(frozen=True)

    entry: ConnectedScheduleEntry = Field(description="Exact executed schedule row.")
    normalized_result_hash: str = Field(description="Authenticated semantic result hash.")
    outcome: RatedOutcome | None = Field(description="Rated outcome from the hero perspective.")
    eligibility: ScientificEligibility = Field(description="Scientific admission decision.")
    adjudication: TerminationAdjudication = Field(description="Typed terminal adjudication.")
    subjectivity_status: str = Field(description="Independent subjectivity witness status.")
    command_count: int = Field(ge=0, description="Commands selected during the match.")
    turn_count: int = Field(ge=0, description="Distinct actor turns represented in command traces.")
    elapsed_ms: float = Field(ge=0.0, description="Measured self-play wall duration.")
    configured_hero_spell_keys: tuple[str, ...] = Field(
        default_factory=tuple,
        description="Implemented spell identities initially available to the hero configuration.",
    )
    configured_monster_spell_keys: tuple[str, ...] = Field(
        default_factory=tuple,
        description="Implemented spell identities initially available to the monster configuration.",
    )
    hero_spell_casts: dict[str, int] = Field(
        default_factory=dict,
        description="Accepted and completed hero spell commands by exact semantic identity.",
    )
    monster_spell_casts: dict[str, int] = Field(
        default_factory=dict,
        description="Accepted and completed monster spell commands by exact semantic identity.",
    )


@dataclass(frozen=True)
class RetainedExperimentEvidence:
    """Authenticated worker evidence and response metadata for one experiment."""

    evidences: dict[str, RetainedMatchAnalysis]
    responses: dict[str, MatchWorkerResponse]
    infrastructure_failures: dict[str, str]
    artifact_bytes: int
    content_coverage: "RetainedContentCoverage" = field(default_factory=lambda: RetainedContentCoverage())


@dataclass
class RetainedContentCoverage:
    """Cross-match lifecycle evidence accumulated while artifacts stream from disk."""

    metadata: dict[str, dict[str, str]] = field(default_factory=dict)
    configured_by_key: dict[str, set[str]] = field(default_factory=lambda: defaultdict(set))
    exposed_by_key: dict[str, set[str]] = field(default_factory=lambda: defaultdict(set))
    affordable_by_key: dict[str, set[str]] = field(default_factory=lambda: defaultdict(set))
    exposed_counts: Counter[str] = field(default_factory=Counter)
    affordable_counts: Counter[str] = field(default_factory=Counter)
    resolved_by_key: dict[str, set[str]] = field(default_factory=lambda: defaultdict(set))
    resolved_counts: Counter[str] = field(default_factory=Counter)
    hero_resolved_counts: Counter[str] = field(default_factory=Counter)
    monster_resolved_counts: Counter[str] = field(default_factory=Counter)
    handler_opportunity_counts: Counter[str] = field(default_factory=Counter)
    handler_effect_counts: Counter[str] = field(default_factory=Counter)
    condition_application_counts: Counter[str] = field(default_factory=Counter)
    condition_removal_counts: Counter[str] = field(default_factory=Counter)
    item_consumption_counts: Counter[str] = field(default_factory=Counter)
    event_lifecycle_counts: Counter[str] = field(default_factory=Counter)
    manifest_match_count: int = 0
    affordance_evidence_match_count: int = 0
    lifecycle_evidence_match_count: int = 0


def build_default_catalog(*, generated_at: str | None = None) -> CatalogSnapshot:
    """Build the complete immutable catalog for the current shared AI policy."""
    policy = policy_source_snapshot()
    return build_catalog_snapshot(
        heroes=HERO_CONFIGURATIONS,
        monster_parties=MONSTER_PARTY_CONFIGURATIONS,
        battlefields=BATTLEFIELDS,
        deployments=DEPLOYMENTS,
        policy_version=policy.policy_version,
        policy_source_hash=policy.source_sha256,
        generated_at=generated_at,
    )


def build_default_schedule(
    catalog: CatalogSnapshot,
    *,
    experiment_id: str,
    seeds: tuple[int, ...] = (20260717,),
    created_at: str | None = None,
) -> ConnectedRatingSchedule:
    """Build the complete connected paired-opening factorial schedule."""
    return build_connected_schedule(
        heroes=catalog.heroes,
        monster_parties=catalog.monster_parties,
        battlefields=catalog.battlefields,
        deployments=catalog.deployments,
        seeds=seeds,
        experiment_id=experiment_id,
        created_at=created_at,
    )


def subset_schedule_by_pair_blocks(
    schedule: ConnectedRatingSchedule,
    *,
    pair_block_count: int,
    experiment_id: str,
) -> ConnectedRatingSchedule:
    """Return evenly spaced complete pairs spanning the full schedule."""
    if pair_block_count < 1:
        raise ValueError("pair_block_count must be at least one.")
    pair_ids: list[str] = []
    for entry in schedule.entries:
        if entry.pair_block_id not in pair_ids:
            pair_ids.append(entry.pair_block_id)
    if len(pair_ids) < pair_block_count:
        raise ValueError("Requested more pair blocks than the schedule contains.")
    if pair_block_count == 1:
        selected_pair_ids = [pair_ids[0]]
    else:
        selected_pair_ids = [
            pair_ids[round(index * (len(pair_ids) - 1) / (pair_block_count - 1))]
            for index in range(pair_block_count)
        ]
    selected = set(selected_pair_ids)
    entries = tuple(
        entry.model_copy(update={"schedule_index": index})
        for index, entry in enumerate(
            entry for entry in schedule.entries if entry.pair_block_id in selected
        )
    )
    schedule_hash = _short_hash({
        "catalog_hash": schedule.catalog_hash,
        "entries": [entry.model_dump(mode="json") for entry in entries],
        "exclusions": [],
    })
    return ConnectedRatingSchedule(
        experiment_id=experiment_id,
        created_at=schedule.created_at,
        catalog_hash=schedule.catalog_hash,
        entries=entries,
        exclusions=(),
        schedule_hash=schedule_hash,
    )


def build_request_factory(
    schedule: ConnectedRatingSchedule,
    catalog: CatalogSnapshot,
    catalog_path: Path,
    *,
    max_commands: int = DEFAULT_RATING_MAX_COMMANDS,
    soft_timeout_seconds: float = 120.0,
) -> RequestFactory:
    """Build immutable real-match requests for an isolated coordinator."""
    resolved_catalog_path = catalog_path.resolve()
    static_runtime_hashes = runtime_hashes_for_entry(schedule.entries[0], catalog)

    def request_factory(
        entry: ConnectedScheduleEntry,
        attempt_number: int,
        dispatch_id: str,
    ) -> MatchWorkerRequest:
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
            expected_runtime_hashes={
                **static_runtime_hashes,
                "hero_configuration": entry.hero_configuration_hash,
                "monster_configuration": entry.monster_configuration_hash,
                "battlefield": entry.battlefield_hash,
                "deployment": entry.deployment_hash,
            },
            catalog_snapshot_path=str(resolved_catalog_path),
            catalog_snapshot_hash=catalog.catalog_hash,
            real_match_entrypoint=REAL_MATCH_ENTRYPOINT,
        )

    return request_factory


def run_schedule_isolated(
    schedule: ConnectedRatingSchedule,
    catalog: CatalogSnapshot,
    catalog_path: Path,
    *,
    output_root: Path,
    spool_root: Path,
    worker_count: int,
    max_commands: int = DEFAULT_RATING_MAX_COMMANDS,
    soft_timeout_seconds: float = 120.0,
    hard_timeout_seconds: float = 135.0,
    max_infrastructure_attempts: int = 2,
) -> ExperimentExecution:
    """Run or resume one schedule using a fresh process for every attempt."""
    request_factory = build_request_factory(
        schedule,
        catalog,
        catalog_path,
        max_commands=max_commands,
        soft_timeout_seconds=soft_timeout_seconds,
    )
    started = time.perf_counter()
    summary = asyncio.run(
        run_isolated_coordinator(
            schedule,
            output_root=output_root,
            spool_root=spool_root,
            request_factory=request_factory,
            worker_count=worker_count,
            hard_timeout_seconds=hard_timeout_seconds,
            max_infrastructure_attempts=max_infrastructure_attempts,
        )
    )
    wall_seconds = time.perf_counter() - started
    experiment_dir = output_root.resolve() / schedule.experiment_id
    measurement = {
        "experiment_id": schedule.experiment_id,
        "schedule_hash": schedule.schedule_hash,
        "worker_count": worker_count,
        "wall_seconds": wall_seconds,
        "spawned_worker_count": summary.spawned_worker_count,
        "resumed_record_count": summary.resumed_record_count,
        "measured_at": datetime.now(timezone.utc).isoformat(),
    }
    atomic_write_json(experiment_dir / "execution.json", measurement, immutable=False)
    return ExperimentExecution(summary=summary, experiment_dir=experiment_dir, wall_seconds=wall_seconds)


def load_retained_evidence(execution: ExperimentExecution) -> RetainedExperimentEvidence:
    """Load authenticated compact analysis fields from canonical artifacts.

    The coordinator has already authenticated and promoted the complete worker
    artifact. This pass rechecks its hashes and cross-record identities while
    retaining only aggregate-analysis fields. Full nested event evidence stays
    on disk and can still be validated or replayed independently.
    """
    evidences: dict[str, RetainedMatchAnalysis] = {}
    responses: dict[str, MatchWorkerResponse] = {}
    failures: dict[str, str] = {}
    artifact_bytes = 0
    content_coverage = RetainedContentCoverage()
    for record in execution.summary.records:
        if record.outcome != AttemptOutcome.COMPLETED or record.artifact_path is None:
            failures[record.entry.match_id] = record.outcome.value
            continue
        artifact_path = execution.experiment_dir / record.artifact_path
        artifact_bytes += artifact_path.stat().st_size
        artifact_value, descriptor = read_gzip_json(artifact_path)
        if descriptor.sha256 != record.artifact_sha256:
            raise ValueError(f"Artifact hash mismatch for {record.entry.match_id}.")
        if descriptor.payload_sha256 != record.artifact_payload_sha256:
            raise ValueError(f"Artifact payload hash mismatch for {record.entry.match_id}.")
        evidence = _retained_match_analysis(
            artifact_value,
            expected_entry=record.entry,
            expected_result_hash=record.normalized_result_hash,
            expected_subjectivity_status=record.subjectivity_status,
            expected_subjectivity_violations=record.subjectivity_violation_count,
            content_coverage=content_coverage,
        )
        receipt = read_json_model(
            execution.experiment_dir / record.receipt_path,
            AttemptReceipt,
        )
        if receipt.response_path is None:
            raise ValueError(f"Completed match lacks a response path: {record.entry.match_id}.")
        response = read_json_model(
            execution.experiment_dir / receipt.response_path,
            MatchWorkerResponse,
        )
        if response.match_id != record.entry.match_id:
            raise ValueError(f"Response match mismatch for {record.entry.match_id}.")
        evidences[record.entry.match_id] = evidence
        responses[record.entry.match_id] = response
    return RetainedExperimentEvidence(
        evidences=evidences,
        responses=responses,
        infrastructure_failures=failures,
        artifact_bytes=artifact_bytes,
        content_coverage=content_coverage,
    )


def _retained_match_analysis(
    artifact_value: object,
    *,
    expected_entry: ConnectedScheduleEntry,
    expected_result_hash: str | None,
    expected_subjectivity_status: str,
    expected_subjectivity_violations: int,
    content_coverage: RetainedContentCoverage | None = None,
) -> RetainedMatchAnalysis:
    """Validate and project one full artifact without retaining its event tree."""
    artifact = _required_mapping(artifact_value, "artifact")
    request = _required_mapping(artifact.get("request"), "artifact.request")
    request_entry = ConnectedScheduleEntry.model_validate(request.get("entry"))
    if request_entry != expected_entry:
        raise ValueError(f"Artifact request entry mismatch for {expected_entry.match_id}.")

    worker_result = _required_mapping(artifact.get("result"), "artifact.result")
    if worker_result.get("status") != "completed":
        raise ValueError(f"Completed artifact has non-completed result for {expected_entry.match_id}.")
    payload = _required_mapping(worker_result.get("payload"), "artifact.result.payload")
    payload_entry = ConnectedScheduleEntry.model_validate(payload.get("entry"))
    if payload_entry != expected_entry:
        raise ValueError(f"Artifact payload entry mismatch for {expected_entry.match_id}.")

    normalized = _required_mapping(
        payload.get("normalized_result"),
        "artifact.result.payload.normalized_result",
    )
    semantic_hash = normalized.get("semantic_hash")
    if not isinstance(semantic_hash, str) or semantic_hash != expected_result_hash:
        raise ValueError(f"Semantic result hash mismatch for {expected_entry.match_id}.")
    if worker_result.get("normalized_result_hash") != semantic_hash:
        raise ValueError(f"Worker result hash mismatch for {expected_entry.match_id}.")

    run_artifact = _required_mapping(
        payload.get("run_artifact"),
        "artifact.result.payload.run_artifact",
    )
    subjectivity = _required_mapping(
        run_artifact.get("subjectivity"),
        "artifact.result.payload.run_artifact.subjectivity",
    )
    subjectivity_status = subjectivity.get("status")
    violations = subjectivity.get("violations")
    if subjectivity_status != expected_subjectivity_status:
        raise ValueError(f"Subjectivity status mismatch for {expected_entry.match_id}.")
    if not isinstance(violations, list) or len(violations) != expected_subjectivity_violations:
        raise ValueError(f"Subjectivity violation count mismatch for {expected_entry.match_id}.")
    if worker_result.get("subjectivity_status") != subjectivity_status:
        raise ValueError(f"Worker subjectivity status mismatch for {expected_entry.match_id}.")
    if worker_result.get("subjectivity_violation_count") != len(violations):
        raise ValueError(f"Worker subjectivity count mismatch for {expected_entry.match_id}.")

    run_result = _required_mapping(
        run_artifact.get("result"),
        "artifact.result.payload.run_artifact.result",
    )
    traces = run_result.get("traces")
    if not isinstance(traces, list):
        raise ValueError(f"Command traces are missing for {expected_entry.match_id}.")
    turns: set[tuple[int, int, str]] = set()
    spell_keys = frozenset(_implemented_spell_catalog())
    spell_casts_by_faction: dict[str, Counter[str]] = {
        "heroes": Counter(),
        "monsters": Counter(),
    }
    for trace_index, trace_value in enumerate(traces):
        trace = _required_mapping(
            trace_value,
            f"artifact.result.payload.run_artifact.result.traces[{trace_index}]",
        )
        round_number = trace.get("round_number")
        turn_index = trace.get("turn_index")
        actor_name = trace.get("actor_name")
        if not isinstance(round_number, int) or not isinstance(turn_index, int) or not isinstance(actor_name, str):
            raise ValueError(f"Invalid command trace identity for {expected_entry.match_id}.")
        turns.add((round_number, turn_index, actor_name))
        semantic_key = trace.get("semantic_key")
        actor_faction = trace.get("actor_faction")
        if (
            trace.get("command_status") == "accepted"
            and trace.get("action_resolution") == "completed"
            and isinstance(semantic_key, str)
            and semantic_key in spell_keys
            and isinstance(actor_faction, str)
            and actor_faction in spell_casts_by_faction
        ):
            spell_casts_by_faction[actor_faction][semantic_key] += 1

    arena_manifest = _required_mapping(
        payload.get("arena_manifest"),
        "artifact.result.payload.arena_manifest",
    )
    if content_coverage is not None:
        _accumulate_content_coverage(
            content_coverage,
            entry=payload_entry,
            arena_manifest=arena_manifest,
            traces=traces,
            match_payload=payload,
        )

    return RetainedMatchAnalysis.model_validate({
        "entry": payload_entry,
        "normalized_result_hash": semantic_hash,
        "outcome": payload.get("outcome"),
        "eligibility": payload.get("eligibility"),
        "adjudication": payload.get("adjudication"),
        "subjectivity_status": subjectivity_status,
        "command_count": run_result.get("command_count"),
        "turn_count": len(turns),
        "elapsed_ms": run_result.get("elapsed_ms"),
        "configured_hero_spell_keys": _configured_spell_keys(arena_manifest, "heroes"),
        "configured_monster_spell_keys": _configured_spell_keys(arena_manifest, "monsters"),
        "hero_spell_casts": dict(sorted(spell_casts_by_faction["heroes"].items())),
        "monster_spell_casts": dict(sorted(spell_casts_by_faction["monsters"].items())),
    })


def _required_mapping(value: object, path: str) -> dict[str, object]:
    """Return one required JSON object with a useful corruption error."""
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object at {path}.")
    return value


def _implemented_spell_catalog() -> dict[str, tuple[str, int]]:
    """Return exact spell semantic keys mapped to display name and level."""
    return {
        f"{spell_type.__module__}.{spell_type.__name__}": (spell_name, level)
        for level, level_spells in _SPELLS_BY_LEVEL
        for spell_name, spell_type in level_spells.items()
    }


def _configured_spell_keys(arena_manifest: dict[str, object], faction: str) -> tuple[str, ...]:
    """Extract initially configured spell identities from one runtime manifest."""
    implemented = _implemented_spell_catalog()
    rosters = _required_mapping(
        arena_manifest.get("entity_rosters"),
        "artifact.result.payload.arena_manifest.entity_rosters",
    )
    roster_rows = rosters.get(faction, [])
    if not isinstance(roster_rows, list):
        raise ValueError(f"Arena manifest roster {faction!r} must be a list.")
    configured: set[str] = set()
    for row_index, row_value in enumerate(roster_rows):
        row = _required_mapping(row_value, f"arena_manifest.entity_rosters.{faction}[{row_index}]")
        action_rows = row.get("action_template_summary", [])
        if not isinstance(action_rows, list):
            raise ValueError("Arena manifest action template summary must be a list.")
        for action_value in action_rows:
            action = _required_mapping(action_value, "arena_manifest.action_template_summary[]")
            semantic_key = action.get("semantic_key")
            if action.get("category") == "spell" and isinstance(semantic_key, str) and semantic_key in implemented:
                configured.add(semantic_key)
        inventory_rows = row.get("inventory_summary", [])
        if not isinstance(inventory_rows, list):
            raise ValueError("Arena manifest inventory summary must be a list.")
        for item_value in inventory_rows:
            item = _required_mapping(item_value, "arena_manifest.inventory_summary[]")
            provided_keys = item.get("provided_spell_semantic_keys")
            if isinstance(provided_keys, list):
                configured.update(
                    key for key in provided_keys
                    if isinstance(key, str) and key in implemented
                )
                continue
            item_name = item.get("name")
            if not isinstance(item_name, str):
                continue
            for spell_name in _ITEM_SPELL_NAMES_BY_DISPLAY.get(item_name, ()):
                spell_type = ALL_SPELLS[spell_name]
                configured.add(f"{spell_type.__module__}.{spell_type.__name__}")
    return tuple(sorted(configured))


def _accumulate_content_coverage(
    coverage: RetainedContentCoverage,
    *,
    entry: ConnectedScheduleEntry,
    arena_manifest: dict[str, object],
    traces: list[object],
    match_payload: dict[str, object],
) -> None:
    """Merge one authenticated match into the general content lifecycle ledger."""
    coverage.manifest_match_count += 1
    rosters = _required_mapping(arena_manifest.get("entity_rosters"), "arena_manifest.entity_rosters")
    faction_configurations = {
        "heroes": entry.hero_configuration_id,
        "monsters": entry.monster_configuration_id,
    }
    for faction, configuration_id in faction_configurations.items():
        roster_rows = rosters.get(faction, [])
        if not isinstance(roster_rows, list):
            raise ValueError(f"Arena manifest roster {faction!r} must be a list.")
        for row_value in roster_rows:
            row = _required_mapping(row_value, f"arena_manifest.entity_rosters.{faction}[]")
            _accumulate_roster_content(coverage, row, configuration_id)

    objects = arena_manifest.get("object_summary", [])
    if isinstance(objects, list):
        battlefield_configuration = f"battlefield:{entry.battlefield_id}"
        for object_value in objects:
            if not isinstance(object_value, dict):
                continue
            semantic_key = object_value.get("semantic_key")
            if not isinstance(semantic_key, str):
                object_class = object_value.get("class")
                if not isinstance(object_class, str):
                    continue
                semantic_key = f"legacy.environment.{object_class}"
            _register_content_metadata(
                coverage,
                semantic_key,
                display_name=str(object_value.get("name") or object_value.get("class") or semantic_key),
                content_kind="environment_interaction",
                subtype="spatial_object",
                identity_quality="typed" if "semantic_key" in object_value else "legacy_class",
            )
            coverage.configured_by_key[semantic_key].add(battlefield_configuration)

    has_affordance_evidence = False
    spell_keys = frozenset(_implemented_spell_catalog())
    for trace_value in traces:
        trace = _required_mapping(trace_value, "run_artifact.result.traces[]")
        actor_faction = trace.get("actor_faction")
        configuration_id = faction_configurations.get(actor_faction) if isinstance(actor_faction, str) else None
        if "available_action_semantic_keys" in trace:
            has_affordance_evidence = True
        for field_name, destination in (
            ("available_action_semantic_keys", coverage.exposed_by_key),
            ("affordable_action_semantic_keys", coverage.affordable_by_key),
        ):
            values = trace.get(field_name, [])
            if not isinstance(values, list) or configuration_id is None:
                continue
            for semantic_key in values:
                if isinstance(semantic_key, str):
                    destination[semantic_key].add(configuration_id)
                    if field_name == "available_action_semantic_keys":
                        coverage.exposed_counts[semantic_key] += 1
                    else:
                        coverage.affordable_counts[semantic_key] += 1
        semantic_key = trace.get("semantic_key")
        if not isinstance(semantic_key, str):
            continue
        action_kind = "spell" if semantic_key in spell_keys else "action"
        _register_content_metadata(
            coverage,
            semantic_key,
            display_name=str(trace.get("template_name") or semantic_key),
            content_kind=action_kind,
            subtype=str(trace.get("action_category") or action_kind),
            identity_quality="typed",
        )
        if (
            trace.get("command_status") == "accepted"
            and trace.get("action_resolution") == "completed"
        ):
            coverage.resolved_counts[semantic_key] += 1
            if configuration_id is not None:
                coverage.resolved_by_key[semantic_key].add(configuration_id)
            if actor_faction == "heroes":
                coverage.hero_resolved_counts[semantic_key] += 1
            elif actor_faction == "monsters":
                coverage.monster_resolved_counts[semantic_key] += 1
    if has_affordance_evidence:
        coverage.affordance_evidence_match_count += 1

    lifecycle_value = match_payload.get("content_coverage")
    if isinstance(lifecycle_value, dict):
        coverage.lifecycle_evidence_match_count += 1
        _merge_counter(coverage.handler_opportunity_counts, lifecycle_value.get("handler_opportunity_counts"))
        _merge_counter(coverage.handler_effect_counts, lifecycle_value.get("handler_effect_counts"))
        _merge_counter(coverage.condition_application_counts, lifecycle_value.get("condition_application_counts"))
        _merge_counter(coverage.condition_removal_counts, lifecycle_value.get("condition_removal_counts"))
        _merge_counter(coverage.item_consumption_counts, lifecycle_value.get("item_consumption_counts"))
        _merge_counter(coverage.event_lifecycle_counts, lifecycle_value.get("event_lifecycle_counts"))
        for metadata_field in ("handler_metadata", "condition_metadata", "item_metadata"):
            metadata = lifecycle_value.get(metadata_field)
            if not isinstance(metadata, dict):
                continue
            for semantic_key, row_value in metadata.items():
                if not isinstance(semantic_key, str) or not isinstance(row_value, dict):
                    continue
                _register_content_metadata(
                    coverage,
                    semantic_key,
                    display_name=str(row_value.get("display_name") or semantic_key),
                    content_kind=str(row_value.get("content_kind") or "unclassified"),
                    subtype=metadata_field.removesuffix("_metadata"),
                    identity_quality="typed",
                )


def _accumulate_roster_content(
    coverage: RetainedContentCoverage,
    row: dict[str, object],
    configuration_id: str,
) -> None:
    """Merge one actor's configured actions, features, handlers, and items."""
    action_rows = row.get("action_template_summary", [])
    if isinstance(action_rows, list):
        for action_value in action_rows:
            if not isinstance(action_value, dict):
                continue
            semantic_key = action_value.get("semantic_key")
            if not isinstance(semantic_key, str):
                continue
            category = str(action_value.get("category") or "action")
            kind = "spell" if category == "spell" else "action"
            _register_content_metadata(
                coverage,
                semantic_key,
                display_name=str(action_value.get("name") or semantic_key),
                content_kind=kind,
                subtype=category,
                identity_quality="typed",
            )
            coverage.configured_by_key[semantic_key].add(configuration_id)

    condition_rows = row.get("condition_summary")
    if isinstance(condition_rows, list):
        for condition_value in condition_rows:
            if not isinstance(condition_value, dict):
                continue
            semantic_key = condition_value.get("semantic_key")
            if not isinstance(semantic_key, str):
                continue
            _register_content_metadata(
                coverage,
                semantic_key,
                display_name=str(condition_value.get("name") or semantic_key),
                content_kind=str(condition_value.get("content_kind") or "condition"),
                subtype=str(condition_value.get("condition_category") or "condition_state"),
                identity_quality="typed",
            )
            coverage.configured_by_key[semantic_key].add(configuration_id)
    else:
        condition_names = row.get("conditions_at_start", [])
        if not isinstance(condition_names, list):
            condition_names = []
        for condition_name in condition_names:
            if not isinstance(condition_name, str):
                continue
            semantic_key = f"legacy.condition.{_coverage_slug(condition_name)}"
            _register_content_metadata(
                coverage,
                semantic_key,
                display_name=condition_name,
                content_kind="condition",
                subtype="legacy_manifest_condition",
                identity_quality="legacy_name",
            )
            coverage.configured_by_key[semantic_key].add(configuration_id)

    handler_rows = row.get("handler_summary")
    if isinstance(handler_rows, list):
        for handler_value in handler_rows:
            if not isinstance(handler_value, dict):
                continue
            semantic_key = handler_value.get("semantic_key")
            if not isinstance(semantic_key, str):
                continue
            _register_content_metadata(
                coverage,
                semantic_key,
                display_name=str(handler_value.get("name") or semantic_key),
                content_kind=str(handler_value.get("content_kind") or "unclassified"),
                subtype="event_handler",
                identity_quality="typed",
            )
            coverage.configured_by_key[semantic_key].add(configuration_id)
    else:
        trait_rows = row.get("trait_summary", [])
        if isinstance(trait_rows, list):
            for trait_name in trait_rows:
                if not isinstance(trait_name, str):
                    continue
                semantic_key = f"legacy.trait_or_handler.{_coverage_slug(trait_name)}"
                _register_content_metadata(
                    coverage,
                    semantic_key,
                    display_name=trait_name,
                    content_kind="unclassified",
                    subtype="legacy_trait_or_handler",
                    identity_quality="legacy_name",
                )
                coverage.configured_by_key[semantic_key].add(configuration_id)

    for item_field in ("equipment_summary", "inventory_summary"):
        item_rows = row.get(item_field, [])
        if not isinstance(item_rows, list):
            continue
        for item_value in item_rows:
            if not isinstance(item_value, dict):
                continue
            semantic_key = item_value.get("semantic_key")
            if not isinstance(semantic_key, str):
                item_class = item_value.get("class")
                if not isinstance(item_class, str):
                    continue
                semantic_key = f"legacy.item.{item_class}"
            _register_content_metadata(
                coverage,
                semantic_key,
                display_name=str(item_value.get("name") or item_value.get("class") or semantic_key),
                content_kind="item",
                subtype="equipped_item" if item_field == "equipment_summary" else "inventory_item",
                identity_quality="typed" if "semantic_key" in item_value else "legacy_class",
            )
            coverage.configured_by_key[semantic_key].add(configuration_id)


def _register_content_metadata(
    coverage: RetainedContentCoverage,
    semantic_key: str,
    *,
    display_name: str,
    content_kind: str,
    subtype: str,
    identity_quality: str,
) -> None:
    """Retain the strongest available stable metadata for one identity."""
    candidate = {
        "display_name": display_name,
        "content_kind": content_kind,
        "subtype": subtype,
        "identity_quality": identity_quality,
    }
    existing = coverage.metadata.get(semantic_key)
    if existing is None or (
        existing.get("identity_quality") != "typed"
        and identity_quality == "typed"
    ):
        coverage.metadata[semantic_key] = candidate


def _merge_counter(counter: Counter[str], value: object) -> None:
    if not isinstance(value, dict):
        return
    for key, count in value.items():
        if isinstance(key, str) and isinstance(count, int) and count >= 0:
            counter[key] += count


def _coverage_slug(value: str) -> str:
    normalized = "".join(character.lower() if character.isalnum() else "." for character in value)
    return ".".join(part for part in normalized.split(".") if part)


def paired_strength_observations(
    schedule: ConnectedRatingSchedule,
    evidence: RetainedExperimentEvidence,
) -> tuple[list[StrengthObservation], dict[str, tuple[str, ...]]]:
    """Admit only complete, scientifically eligible opening pairs."""
    entries_by_pair: dict[str, list[ConnectedScheduleEntry]] = defaultdict(list)
    for entry in schedule.entries:
        entries_by_pair[entry.pair_block_id].append(entry)
    observations: list[StrengthObservation] = []
    excluded_pairs: dict[str, tuple[str, ...]] = {}
    for pair_block_id, entries in sorted(entries_by_pair.items()):
        reasons: set[str] = set()
        if len(entries) != 2 or {row.opening_treatment for row in entries} != {"hero_first", "monster_first"}:
            reasons.add("schedule_pair_incomplete")
        pair_evidence = []
        for entry in entries:
            retained = evidence.evidences.get(entry.match_id)
            if retained is None:
                reasons.add(f"missing_evidence:{entry.match_id}")
                continue
            pair_evidence.append(retained)
            if not retained.eligibility.eligible:
                reasons.update(retained.eligibility.reasons)
            if retained.outcome is None:
                reasons.add("unknown_outcome")
        if reasons:
            excluded_pairs[pair_block_id] = tuple(sorted(reasons))
            continue
        for retained in pair_evidence:
            if retained.outcome is None:
                raise ValueError(f"Pair {pair_block_id} passed admission without an outcome.")
            observations.append(StrengthObservation(
                match_id=retained.entry.match_id,
                pair_block_id=retained.entry.pair_block_id,
                hero_configuration_id=retained.entry.hero_configuration_id,
                monster_configuration_id=retained.entry.monster_configuration_id,
                battlefield_id=retained.entry.battlefield_id,
                deployment_id=retained.entry.deployment_id,
                opening_treatment=retained.entry.opening_treatment,
                outcome=retained.outcome,
            ))
    return observations, excluded_pairs


def scaling_pilot_from_execution(
    execution: ExperimentExecution,
    evidence: RetainedExperimentEvidence,
    *,
    workload_hash: str,
    worker_count: int,
    determinism_canaries_passed: bool,
) -> ScalingPilot:
    """Derive one scaling row solely from retained coordinator evidence."""
    eligible = sum(row.eligibility.eligible for row in evidence.evidences.values())
    completed = sum(
        record.outcome == AttemptOutcome.COMPLETED
        for record in execution.summary.records
    )
    total_cpu = sum(
        response.timing.user_cpu_seconds + response.timing.system_cpu_seconds
        for response in evidence.responses.values()
    )
    peak_worker_rss = max(
        (response.timing.peak_rss_mb for response in evidence.responses.values()),
        default=0.0,
    )
    measured_wall_seconds = _active_wall_seconds(evidence.responses.values()) or execution.wall_seconds
    return ScalingPilot(
        worker_count=worker_count,
        workload_hash=workload_hash,
        scheduled_matches=len(execution.summary.records),
        completed_matches=completed,
        eligible_matches=eligible,
        wall_seconds=measured_wall_seconds,
        total_worker_cpu_seconds=total_cpu,
        peak_rss_mb=peak_worker_rss,
        failure_count=len(execution.summary.records) - eligible,
        determinism_canaries_passed=determinism_canaries_passed,
    )


def run_scaling_pilots(
    full_schedule: ConnectedRatingSchedule,
    catalog: CatalogSnapshot,
    catalog_path: Path,
    *,
    output_root: Path,
    spool_root: Path,
    worker_counts: tuple[int, ...] = (1, 4, 8, 12, 16),
    pair_block_count: int = 16,
    max_commands: int = DEFAULT_RATING_MAX_COMMANDS,
) -> tuple[ParallelScalingAnalysis, tuple[ScalingPilot, ...]]:
    """Run comparable real-match pilots and audit cross-concurrency determinism."""
    raw_rows: list[tuple[int, ExperimentExecution, RetainedExperimentEvidence]] = []
    baseline_hashes: dict[str, str] | None = None
    for worker_count in worker_counts:
        pilot_schedule = subset_schedule_by_pair_blocks(
            full_schedule,
            pair_block_count=pair_block_count,
            experiment_id=f"{full_schedule.experiment_id}-scaling-w{worker_count}",
        )
        execution = run_schedule_isolated(
            pilot_schedule,
            catalog,
            catalog_path,
            output_root=output_root,
            spool_root=spool_root,
            worker_count=worker_count,
            max_commands=max_commands,
        )
        evidence = load_retained_evidence(execution)
        hashes = {
            match_id: row.normalized_result_hash
            for match_id, row in evidence.evidences.items()
        }
        if baseline_hashes is None:
            baseline_hashes = hashes
        raw_rows.append((worker_count, execution, evidence))
    if baseline_hashes is None:
        raise ValueError("Scaling study produced no baseline semantic hashes.")
    pilots = tuple(
        scaling_pilot_from_execution(
            execution,
            evidence,
            workload_hash=subset_schedule_by_pair_blocks(
                full_schedule,
                pair_block_count=pair_block_count,
                experiment_id="scaling-workload-identity",
            ).schedule_hash,
            worker_count=worker_count,
            determinism_canaries_passed={
                match_id: row.normalized_result_hash
                for match_id, row in evidence.evidences.items()
            } == baseline_hashes,
        )
        for worker_count, execution, evidence in raw_rows
    )
    return analyze_parallel_scaling(pilots), pilots


def build_experiment_report(
    schedule: ConnectedRatingSchedule,
    catalog: CatalogSnapshot,
    execution: ExperimentExecution,
    evidence: RetainedExperimentEvidence,
    *,
    scaling: ParallelScalingAnalysis | None = None,
    scaling_pilots: tuple[ScalingPilot, ...] = (),
    bootstrap_replicates: int = 500,
    bootstrap_seed: int = 20260717,
) -> dict[str, object]:
    """Analyze retained evidence and build the renderer's strict JSON source."""
    observations, excluded_pairs = paired_strength_observations(schedule, evidence)
    strength = fit_configuration_strength(observations) if observations else None
    provisional = build_provisional_paired_elo(observations) if observations else None
    order_audit = (
        audit_elo_order_sensitivity(observations, permutation_count=250, random_seed=bootstrap_seed)
        if observations
        else None
    )
    bootstrap = (
        bootstrap_configuration_strength(
            observations,
            replicate_count=bootstrap_replicates,
            random_seed=bootstrap_seed,
        )
        if observations
        else None
    )
    scheduled_count = len(schedule.entries)
    completed_count = len(evidence.evidences)
    eligible_count = len(observations)
    subjectivity_failures = sum(
        row.subjectivity_status != "passed"
        for row in evidence.evidences.values()
    )
    all_complete = completed_count == scheduled_count
    all_eligible = eligible_count == scheduled_count and not excluded_pairs
    outcome_counts = {
        outcome.value: sum(row.outcome == outcome for row in observations)
        for outcome in RatedOutcome
    }
    adjudication_counts: dict[str, int] = defaultdict(int)
    for row in evidence.evidences.values():
        adjudication_counts[row.adjudication.kind] += 1
    connectivity = schedule_connectivity(schedule)
    performance = _performance_report(execution, evidence)
    scaling_report = _scaling_report(scaling, scaling_pilots)
    report: dict[str, object] = {
        "schema_version": 1,
        "source": {
            "experiment_id": schedule.experiment_id,
            "title": "NeuroDragon Connected Configuration Power Gauntlet",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "schedule_hash": schedule.schedule_hash,
            "catalog_hash": catalog.catalog_hash,
            "policy_version": catalog.policy_version,
            "policy_source_hash": catalog.policy_source_hash,
            "ruleset_id": catalog.ruleset_id,
        },
        "status": {
            "phase": "completed" if all_complete and all_eligible else "partial",
            "scheduled_matches": scheduled_count,
            "completed_matches": completed_count,
            "eligible_matches": eligible_count,
            "failed_matches": scheduled_count - eligible_count,
            "scheduled_pair_blocks": len(schedule.entries_by_pair_block()),
            "completed_pair_blocks": len(observations) // 2,
            "excluded_pair_blocks": len(excluded_pairs),
            "hero_wins": outcome_counts[RatedOutcome.HERO_WIN.value],
            "monster_wins": outcome_counts[RatedOutcome.MONSTER_WIN.value],
            "draws": outcome_counts[RatedOutcome.DRAW.value],
            "natural_ends": adjudication_counts.get("natural_end", 0),
            "stalemate_draws": adjudication_counts.get("stalemate_draw", 0),
        },
        "method": {
            "primary_estimator": strength.estimator if strength is not None else "not fitted",
            "primary_scale": "adjusted Elo, centered at 1000 within each side table",
            "paired_openings": True,
            "factorial_design": "hero configuration x monster-party configuration x battlefield x opening treatment",
            "bootstrap": f"paired-block bootstrap, {bootstrap_replicates} replicates",
            "provisional_secondary": "paired-block online Elo with order-sensitivity audit",
            "subjectivity": "server-issued subjective epochs and independent perception witness",
            "stalemate_draw_rule": (
                "80 consecutive accepted commands with no change to the complete "
                "combatant HP vector; objective samples are evaluator-only"
            ),
        },
        "quality": {
            "completion": {
                "status": "passed" if all_complete else "failed",
                "detail": f"{completed_count} of {scheduled_count} disposable workers produced authenticated evidence.",
            },
            "scientific_admission": {
                "status": "passed" if all_eligible else "failed",
                "detail": f"{eligible_count} matches in complete opening pairs entered the model; {len(excluded_pairs)} pairs were excluded.",
            },
            "subjectivity": {
                "status": "passed" if subjectivity_failures == 0 else "failed",
                "detail": f"{subjectivity_failures} retained matches failed the independent disclosure audit.",
            },
            "connectivity": {
                "status": "passed" if connectivity.connected else "failed",
                "detail": f"The participant graph has {connectivity.component_count} component(s) and {connectivity.edge_count} distinct pairings.",
            },
            "model": {
                "status": "passed" if strength is not None and strength.publishable else "failed",
                "detail": "Adjusted model publication gates passed." if strength is not None and strength.publishable else "Adjusted model publication gates did not pass.",
            },
            "adjudication": {
                "status": "passed" if adjudication_counts.get("unresolved", 0) == 0 else "failed",
                "detail": f"{adjudication_counts.get('natural_end', 0)} encounters ended naturally and {adjudication_counts.get('stalemate_draw', 0)} met the declared no-progress draw horizon.",
            },
            "bootstrap": {
                "status": "passed" if bootstrap is not None and bootstrap.publishable else "failed",
                "detail": f"{bootstrap.successful_replicates} of {bootstrap.requested_replicates} paired resamples succeeded." if bootstrap is not None else "Bootstrap was unavailable.",
            },
            "determinism": {
                "status": "passed" if scaling_pilots and all(row.determinism_canaries_passed for row in scaling_pilots) else "unavailable",
                "detail": "Semantic hashes matched across all measured worker counts." if scaling_pilots and all(row.determinism_canaries_passed for row in scaling_pilots) else "Cross-concurrency canaries were not all available.",
            },
        },
        "participants": {
            "heroes": len(catalog.heroes),
            "monster_parties": len(catalog.monster_parties),
            "battlefields": len(tuple(row for row in catalog.battlefields if row.portable)),
            "deployments": len(tuple(row for row in catalog.deployments if row.portable and row.rating_eligible)),
        },
        "strength_result": strength.model_dump(mode="json") if strength is not None else {},
        "connectivity": connectivity.model_dump(mode="json"),
        "predicted_matchups": _predicted_matchups(strength),
        "empirical_matchups": _empirical_matchups(observations),
        "specialization": _specialization_rows(observations),
        "rank_uncertainty": _rank_uncertainty_rows(bootstrap),
        "calibration": _calibration_rows(observations, strength),
        "spell_coverage": build_spell_coverage_report(catalog, evidence),
        "content_coverage": build_content_coverage_report(catalog, evidence),
        "performance": performance,
        "scaling": scaling_report,
        "artifacts": _artifact_rows(execution, catalog),
        "explanations": {
            "hero_strength": "Adjusted Elo controls for opponent configuration, battlefield, and opening treatment. Intervals in the forest plot are observed-information diagnostics; bootstrap rank uncertainty is reported separately.",
            "monster_strength": "Monster-party strength is estimated on the same connected scale, with larger values indicating a stronger party.",
            "context_effects": "Positive battlefield and opening effects increase hero log odds after controlling for both configurations.",
            "predicted_matchups": "Cells are average-context hero win probabilities implied by the order-independent adjusted strength model.",
            "empirical_matchups": "Cells aggregate all retained battlefields and both opening treatments for the exact configuration pair.",
            "specialization": "Residual Elo compares a configuration's smoothed battlefield score with its own global score; positive values mean that battlefield suits the configuration.",
            "spell_coverage": "Implemented spells come from dnd.spells.ALL_SPELLS. Configured spells were initially available through a combatant action or spell item, while exercised spells are exact semantic identities from accepted and completed commands.",
            "content_coverage": "Each content family uses its own engine-native lifecycle: decision epochs and completed commands for actions, matched and effecting dispatches for reactions and passive handlers, condition lifecycle events for statuses and features, and item resource events for finite item use.",
            "runtime_phases": "Task, artifact serialization, and interpreter/orchestration overhead are summed from authenticated worker responses.",
            "completion": "The cumulative line is generated from worker start and completion timestamps retained in response JSON.",
            "scaling": "Every worker-count pilot ran the identical real-match pair-block workload. Peak RSS is the largest measured individual worker peak, not a fabricated aggregate estimate.",
        },
        "secondary_estimators": {
            "provisional_paired_elo": provisional.model_dump(mode="json") if provisional is not None else None,
            "elo_order_sensitivity": order_audit.model_dump(mode="json") if order_audit is not None else None,
            "paired_bootstrap": bootstrap.model_dump(mode="json") if bootstrap is not None else None,
        },
        "excluded_pairs": excluded_pairs,
        "infrastructure_failures": evidence.infrastructure_failures,
    }
    return build_report_projection(report)


def build_spell_coverage_report(
    catalog: CatalogSnapshot,
    evidence: RetainedExperimentEvidence,
) -> dict[str, object]:
    """Aggregate implemented, configured, and exercised spell coverage.

    Args:
        catalog: Immutable participant catalog used by the experiment.
        evidence: Compact authenticated match projections containing semantic
            availability and accepted-cast counts.

    Returns:
        Strict JSON-compatible spell coverage summary and per-spell rows.
    """
    implemented = _implemented_spell_catalog()
    configured_by_spell: dict[str, set[str]] = defaultdict(set)
    casting_configurations_by_spell: dict[str, set[str]] = defaultdict(set)
    hero_casts: Counter[str] = Counter()
    monster_casts: Counter[str] = Counter()

    for match in evidence.evidences.values():
        hero_id = match.entry.hero_configuration_id
        monster_id = match.entry.monster_configuration_id
        for semantic_key in match.configured_hero_spell_keys:
            configured_by_spell[semantic_key].add(hero_id)
        for semantic_key in match.configured_monster_spell_keys:
            configured_by_spell[semantic_key].add(monster_id)
        for semantic_key, count in match.hero_spell_casts.items():
            hero_casts[semantic_key] += count
            casting_configurations_by_spell[semantic_key].add(hero_id)
        for semantic_key, count in match.monster_spell_casts.items():
            monster_casts[semantic_key] += count
            casting_configurations_by_spell[semantic_key].add(monster_id)

    rows: list[dict[str, object]] = []
    by_level: list[dict[str, object]] = []
    for level in range(10):
        level_keys = {
            semantic_key
            for semantic_key, (_name, spell_level) in implemented.items()
            if spell_level == level
        }
        configured_level = level_keys & configured_by_spell.keys()
        exercised_level = {
            semantic_key
            for semantic_key in level_keys
            if hero_casts[semantic_key] + monster_casts[semantic_key] > 0
        }
        by_level.append({
            "level": level,
            "implemented_spells": len(level_keys),
            "configured_spells": len(configured_level),
            "exercised_spells": len(exercised_level),
            "casts": sum(hero_casts[key] + monster_casts[key] for key in level_keys),
        })

    for semantic_key, (spell_name, level) in sorted(
        implemented.items(),
        key=lambda item: (item[1][1], item[1][0]),
    ):
        hero_count = hero_casts[semantic_key]
        monster_count = monster_casts[semantic_key]
        cast_count = hero_count + monster_count
        configured_ids = sorted(configured_by_spell.get(semantic_key, set()))
        casting_ids = sorted(casting_configurations_by_spell.get(semantic_key, set()))
        status = "exercised" if cast_count else "configured_unused" if configured_ids else "unconfigured"
        rows.append({
            "spell_name": spell_name,
            "semantic_key": semantic_key,
            "spell_level": level,
            "status": status,
            "cast_count": cast_count,
            "hero_cast_count": hero_count,
            "monster_cast_count": monster_count,
            "configured_configuration_ids": configured_ids,
            "casting_configuration_ids": casting_ids,
        })

    implemented_count = len(implemented)
    configured_keys = set(implemented) & configured_by_spell.keys()
    exercised_keys = {
        semantic_key
        for semantic_key in implemented
        if hero_casts[semantic_key] + monster_casts[semantic_key] > 0
    }
    configured_count = len(configured_keys)
    exercised_count = len(exercised_keys)
    total_casts = sum(hero_casts.values()) + sum(monster_casts.values())
    return {
        "implemented_spell_count": implemented_count,
        "configured_spell_count": configured_count,
        "exercised_spell_count": exercised_count,
        "configured_but_unused_count": len(configured_keys - exercised_keys),
        "implemented_but_unconfigured_count": len(set(implemented) - configured_keys),
        "total_spell_casts": total_casts,
        "hero_spell_casts": sum(hero_casts.values()),
        "monster_spell_casts": sum(monster_casts.values()),
        "configuration_coverage_pct": 100.0 * configured_count / implemented_count,
        "exercise_coverage_pct": 100.0 * exercised_count / implemented_count,
        "configured_exercise_pct": 100.0 * exercised_count / configured_count if configured_count else 0.0,
        "configuration_count": len(catalog.heroes) + len(catalog.monster_parties),
        "match_count": len(evidence.evidences),
        "by_level": by_level,
        "spells": rows,
    }


def build_content_coverage_report(
    catalog: CatalogSnapshot,
    evidence: RetainedExperimentEvidence,
) -> dict[str, object]:
    """Build a typed lifecycle ledger for all discoverable rules content."""
    implemented = build_implemented_content_catalog()
    retained = evidence.content_coverage
    observed_keys = set(retained.metadata)
    observed_keys.update(retained.configured_by_key)
    observed_keys.update(retained.exposed_counts)
    observed_keys.update(retained.resolved_counts)
    observed_keys.update(retained.handler_opportunity_counts)
    observed_keys.update(retained.handler_effect_counts)
    observed_keys.update(retained.condition_application_counts)
    observed_keys.update(retained.condition_removal_counts)
    observed_keys.update(retained.item_consumption_counts)
    for semantic_key in tuple(observed_keys):
        parent_key, separator, _handler_suffix = semantic_key.partition(".handler.")
        parent = implemented.get(parent_key) if separator else None
        if parent is None:
            continue
        runtime_metadata = retained.metadata.get(semantic_key, {})
        implemented[semantic_key] = parent.model_copy(update={
            "semantic_key": semantic_key,
            "display_name": runtime_metadata.get("display_name", parent.display_name),
            "subtype": "owned_event_handler",
            "source_class": f"{parent.source_class} handler",
            "evidence_lifecycle": "handler_dispatch",
        })
    all_keys = set(implemented) | observed_keys

    rows: list[dict[str, object]] = []
    family_counters: dict[str, Counter[str]] = defaultdict(Counter)
    subtype_counters: dict[tuple[str, str], Counter[str]] = defaultdict(Counter)
    for semantic_key in all_keys:
        definition = implemented.get(semantic_key)
        runtime_metadata = retained.metadata.get(semantic_key, {})
        content_kind = (
            definition.content_kind.value
            if definition is not None
            else runtime_metadata.get("content_kind", "unclassified")
        )
        subtype = (
            definition.subtype
            if definition is not None
            else runtime_metadata.get("subtype", "unclassified")
        )
        configured_ids = sorted(retained.configured_by_key.get(semantic_key, set()))
        exposed_ids = sorted(retained.exposed_by_key.get(semantic_key, set()))
        resolved_ids = sorted(retained.resolved_by_key.get(semantic_key, set()))
        exposure_count = retained.exposed_counts[semantic_key]
        affordable_count = retained.affordable_counts[semantic_key]
        resolved_count = retained.resolved_counts[semantic_key]
        handler_opportunities = retained.handler_opportunity_counts[semantic_key]
        handler_effects = retained.handler_effect_counts[semantic_key]
        condition_applications = retained.condition_application_counts[semantic_key]
        condition_removals = retained.condition_removal_counts[semantic_key]
        item_consumptions = retained.item_consumption_counts[semantic_key]
        opportunity_count = exposure_count + handler_opportunities
        effect_count = resolved_count + handler_effects + condition_applications + item_consumptions
        implemented_here = definition is not None
        configured = bool(configured_ids)
        if effect_count:
            status = "effected"
        elif opportunity_count:
            status = "opportunity_only"
        elif configured:
            status = "configured_unexercised"
        elif implemented_here:
            status = "implemented_unconfigured"
        else:
            status = "observed_uncatalogued"
        display_name = (
            definition.display_name
            if definition is not None
            else runtime_metadata.get("display_name", semantic_key)
        )
        lifecycle = (
            definition.evidence_lifecycle
            if definition is not None
            else runtime_metadata.get("subtype", "runtime_observation")
        )
        row = {
            "semantic_key": semantic_key,
            "display_name": display_name,
            "content_kind": content_kind,
            "subtype": subtype,
            "status": status,
            "implemented": implemented_here,
            "identity_quality": runtime_metadata.get(
                "identity_quality",
                "catalogued" if implemented_here else "runtime_only",
            ),
            "evidence_lifecycle": lifecycle,
            "configured_configuration_ids": configured_ids,
            "exposed_configuration_ids": exposed_ids,
            "effecting_configuration_ids": resolved_ids,
            "exposure_count": exposure_count,
            "affordable_exposure_count": affordable_count,
            "resolved_command_count": resolved_count,
            "hero_resolved_command_count": retained.hero_resolved_counts[semantic_key],
            "monster_resolved_command_count": retained.monster_resolved_counts[semantic_key],
            "handler_opportunity_count": handler_opportunities,
            "handler_effect_count": handler_effects,
            "condition_application_count": condition_applications,
            "condition_removal_count": condition_removals,
            "item_consumption_count": item_consumptions,
            "effect_count": effect_count,
        }
        rows.append(row)
        family = family_counters[content_kind]
        subtype_counter = subtype_counters[(content_kind, subtype)]
        for counter in (family, subtype_counter):
            counter["identity_count"] += 1
            counter["implemented_count"] += int(implemented_here)
            counter["configured_count"] += int(configured)
            counter["opportunity_identity_count"] += int(opportunity_count > 0)
            counter["effected_identity_count"] += int(effect_count > 0)
            counter["opportunity_count"] += opportunity_count
            counter["effect_count"] += effect_count

    rows.sort(key=lambda row: (
        str(row["content_kind"]),
        str(row["subtype"]),
        str(row["display_name"]),
        str(row["semantic_key"]),
    ))
    by_family = [
        {"content_kind": kind, **dict(counts)}
        for kind, counts in sorted(family_counters.items())
    ]
    by_subtype = [
        {"content_kind": kind, "subtype": subtype, **dict(counts)}
        for (kind, subtype), counts in sorted(subtype_counters.items())
    ]
    implemented_keys = set(implemented)
    configured_implemented = implemented_keys & retained.configured_by_key.keys()
    effected_implemented = {
        key for key in implemented_keys
        if (
            retained.resolved_counts[key]
            + retained.handler_effect_counts[key]
            + retained.condition_application_counts[key]
            + retained.item_consumption_counts[key]
        ) > 0
    }
    return {
        "implemented_identity_count": len(implemented_keys),
        "configured_implemented_identity_count": len(configured_implemented),
        "effected_implemented_identity_count": len(effected_implemented),
        "configured_but_uneffected_count": len(configured_implemented - effected_implemented),
        "implemented_but_unconfigured_count": len(implemented_keys - configured_implemented),
        "observed_uncatalogued_identity_count": len(observed_keys - implemented_keys),
        "legacy_identity_count": sum(
            1 for row in rows if str(row["identity_quality"]).startswith("legacy")
        ),
        "configuration_coverage_pct": (
            100.0 * len(configured_implemented) / len(implemented_keys)
            if implemented_keys else 0.0
        ),
        "effect_coverage_pct": (
            100.0 * len(effected_implemented) / len(implemented_keys)
            if implemented_keys else 0.0
        ),
        "configured_effect_pct": (
            100.0 * len(effected_implemented & configured_implemented) / len(configured_implemented)
            if configured_implemented else 0.0
        ),
        "manifest_match_count": retained.manifest_match_count,
        "affordance_evidence_match_count": retained.affordance_evidence_match_count,
        "lifecycle_evidence_match_count": retained.lifecycle_evidence_match_count,
        "match_count": len(evidence.evidences),
        "configuration_count": len(catalog.heroes) + len(catalog.monster_parties),
        "by_family": by_family,
        "by_subtype": by_subtype,
        "event_lifecycle_counts": [
            {"event_lifecycle": key, "count": count}
            for key, count in sorted(retained.event_lifecycle_counts.items())
        ],
        "content": rows,
    }


def write_experiment_report(
    report: dict[str, object],
    *,
    experiment_dir: Path,
    html_copy_path: Path | None = None,
) -> tuple[Path, Path]:
    """Write strict report JSON and a self-contained offline HTML visualization."""
    json_path = experiment_dir / "report.json"
    html_path = experiment_dir / "report.html"
    atomic_write_json(json_path, report, immutable=False)
    write_report_html(report, html_path)
    if html_copy_path is not None:
        write_report_html(report, html_copy_path)
    return json_path, html_path


def _performance_report(
    execution: ExperimentExecution,
    evidence: RetainedExperimentEvidence,
) -> dict[str, object]:
    responses = tuple(evidence.responses.values())
    wall_seconds = _active_wall_seconds(responses) or execution.wall_seconds
    command_count = sum(row.command_count for row in evidence.evidences.values())
    turn_count = sum(row.turn_count for row in evidence.evidences.values())
    total_cpu = sum(row.timing.user_cpu_seconds + row.timing.system_cpu_seconds for row in responses)
    peak_rss = max((row.timing.peak_rss_mb for row in responses), default=0.0)
    task_ms = sum(row.timing.task_ms for row in responses)
    serialization_ms = sum(row.timing.serialization_ms for row in responses)
    worker_total_ms = sum(row.timing.total_ms for row in responses)
    overhead_ms = max(0.0, worker_total_ms - task_ms - serialization_ms)
    aggregate = max(1e-9, task_ms + serialization_ms + overhead_ms)
    return {
        "wall_time_ms": wall_seconds * 1000.0,
        "matches_per_second": len(evidence.evidences) / wall_seconds if wall_seconds else 0.0,
        "turns_per_second": turn_count / wall_seconds if wall_seconds else 0.0,
        "commands_per_second": command_count / wall_seconds if wall_seconds else 0.0,
        "cpu_utilization_pct": 100.0 * total_cpu / wall_seconds if wall_seconds else 0.0,
        "peak_rss_mb": peak_rss,
        "artifact_bytes": evidence.artifact_bytes,
        "match_elapsed_ms": _distribution(
            [row.elapsed_ms for row in evidence.evidences.values()]
        ),
        "worker_total_ms": _distribution([row.timing.total_ms for row in responses]),
        "phase_timings": [
            {"phase": "subjective simulation and audit", "total_ms": task_ms, "share_pct": 100.0 * task_ms / aggregate},
            {"phase": "artifact serialization", "total_ms": serialization_ms, "share_pct": 100.0 * serialization_ms / aggregate},
            {"phase": "worker process overhead", "total_ms": overhead_ms, "share_pct": 100.0 * overhead_ms / aggregate},
        ],
        "completion_series": _completion_series(responses),
    }


def _scaling_report(
    analysis: ParallelScalingAnalysis | None,
    pilots: tuple[ScalingPilot, ...],
) -> dict[str, object]:
    if analysis is None:
        return {}
    pilots_by_worker = {row.worker_count: row for row in pilots}
    return {
        "selected_worker_count": analysis.selected_worker_count,
        "selection_reason": analysis.selection_reason,
        "pilots": [
            {
                "workers": row.worker_count,
                "wall_time_ms": row.wall_seconds * 1000.0,
                "throughput_matches_per_second": row.matches_per_second,
                "speedup": row.speedup,
                "parallel_efficiency_pct": row.parallel_efficiency * 100.0,
                "cpu_utilization_pct": row.cpu_utilization_equivalent * 100.0,
                "peak_rss_mb": row.peak_rss_mb,
                "failure_rate_pct": row.failure_rate * 100.0,
                "eligible_matches": pilots_by_worker[row.worker_count].eligible_matches,
                "determinism_canaries_passed": row.determinism_canaries_passed,
            }
            for row in analysis.rows
        ],
    }


def _predicted_matchups(strength: object | None) -> dict[str, object]:
    if strength is None:
        return {}
    hero_ratings = getattr(strength, "hero_ratings")
    monster_ratings = getattr(strength, "monster_ratings")
    cells = []
    for hero in hero_ratings:
        for monster in monster_ratings:
            probability = 1.0 / (1.0 + 10.0 ** ((monster.adjusted_elo - hero.adjusted_elo) / 400.0))
            cells.append({
                "row_id": hero.configuration_id,
                "column_id": monster.configuration_id,
                "probability": probability,
            })
    return {
        "row_ids": [row.configuration_id for row in hero_ratings],
        "column_ids": [row.configuration_id for row in monster_ratings],
        "cells": cells,
    }


def _empirical_matchups(observations: list[StrengthObservation]) -> dict[str, object]:
    grouped: dict[tuple[str, str], list[StrengthObservation]] = defaultdict(list)
    for row in observations:
        grouped[(row.hero_configuration_id, row.monster_configuration_id)].append(row)
    cells = []
    for (hero_id, monster_id), rows in sorted(grouped.items()):
        wins = sum(row.outcome == RatedOutcome.HERO_WIN for row in rows)
        losses = sum(row.outcome == RatedOutcome.MONSTER_WIN for row in rows)
        draws = len(rows) - wins - losses
        cells.append({
            "row_id": hero_id,
            "column_id": monster_id,
            "probability": (wins + 0.5 * draws) / len(rows),
            "wins": wins,
            "losses": losses,
            "draws": draws,
            "games": len(rows),
        })
    return {
        "row_ids": sorted({row.hero_configuration_id for row in observations}),
        "column_ids": sorted({row.monster_configuration_id for row in observations}),
        "cells": cells,
    }


def _specialization_rows(observations: list[StrengthObservation]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for side_kind in ("hero", "monster_party"):
        config_ids = sorted({
            row.hero_configuration_id if side_kind == "hero" else row.monster_configuration_id
            for row in observations
        })
        for configuration_id in config_ids:
            config_rows = [
                row for row in observations
                if (row.hero_configuration_id if side_kind == "hero" else row.monster_configuration_id) == configuration_id
            ]
            overall = _smoothed_score(config_rows, side_kind)
            for battlefield_id in sorted({row.battlefield_id for row in config_rows}):
                field_rows = [row for row in config_rows if row.battlefield_id == battlefield_id]
                field_score = _smoothed_score(field_rows, side_kind)
                residual = 400.0 * math.log10(
                    (field_score / (1.0 - field_score))
                    / (overall / (1.0 - overall))
                )
                rows.append({
                    "configuration_id": configuration_id,
                    "side_kind": side_kind,
                    "battlefield_id": battlefield_id,
                    "residual_elo": residual,
                    "games": len(field_rows),
                })
    rows.sort(key=_specialization_sort_key)
    return rows


def _specialization_sort_key(row: dict[str, object]) -> tuple[float, str, str]:
    value = row.get("residual_elo")
    residual = float(value) if isinstance(value, (int, float)) else 0.0
    return -abs(residual), str(row.get("configuration_id")), str(row.get("battlefield_id"))


def _rank_uncertainty_rows(bootstrap: object | None) -> list[dict[str, object]]:
    if bootstrap is None:
        return []
    intervals = (*getattr(bootstrap, "hero_intervals"), *getattr(bootstrap, "monster_intervals"))
    return [
        {
            "configuration_id": row.configuration_id,
            "side_kind": row.side_kind,
            "lower_rank": row.rank_lower_95,
            "median_rank": row.rank_median,
            "upper_rank": row.rank_upper_95,
            "top_n_probability": row.top_n_probability,
            "elo_lower_95": row.elo_lower_95,
            "elo_median": row.elo_median,
            "elo_upper_95": row.elo_upper_95,
        }
        for row in intervals
    ]


def _calibration_rows(
    observations: list[StrengthObservation],
    strength: object | None,
) -> list[dict[str, object]]:
    if strength is None:
        return []
    hero_elo = {row.configuration_id: row.adjusted_elo for row in getattr(strength, "hero_ratings")}
    monster_elo = {row.configuration_id: row.adjusted_elo for row in getattr(strength, "monster_ratings")}
    effects = {(row.context_kind, row.context_id): row.coefficient for row in getattr(strength, "context_effects")}
    buckets: dict[int, list[tuple[float, float]]] = defaultdict(list)
    for row in observations:
        base_log_odds = math.log(10.0) * (
            hero_elo[row.hero_configuration_id] - monster_elo[row.monster_configuration_id]
        ) / 400.0
        context = effects.get(("battlefield", row.battlefield_id), 0.0)
        opening = effects.get(("opening", "hero_first_minus_monster_first"), 0.0)
        eta = base_log_odds + context + (0.5 if row.opening_treatment == "hero_first" else -0.5) * opening
        predicted = 1.0 / (1.0 + math.exp(-eta))
        observed = 1.0 if row.outcome == RatedOutcome.HERO_WIN else 0.0 if row.outcome == RatedOutcome.MONSTER_WIN else 0.5
        buckets[min(4, int(predicted * 5.0))].append((predicted, observed))
    return [
        {
            "label": f"{index * 20}-{(index + 1) * 20}%",
            "predicted_probability": fmean(value[0] for value in values),
            "observed_rate": fmean(value[1] for value in values),
            "count": len(values),
        }
        for index, values in sorted(buckets.items())
    ]


def _artifact_rows(execution: ExperimentExecution, catalog: CatalogSnapshot) -> list[dict[str, object]]:
    return [
        {"artifact_id": "catalog", "kind": "typed catalog snapshot", "path": "../inputs/catalog.json", "sha256": catalog.catalog_hash},
        {"artifact_id": "schedule", "kind": "immutable connected schedule", "path": "schedule.json", "sha256": execution.summary.schedule_hash},
        {"artifact_id": "coordinator-summary", "kind": "canonical process-isolation summary", "path": "summary.json"},
        {"artifact_id": "compressed-matches", "kind": "per-match gzip JSON evidence", "path": "attempts/"},
    ]


def _smoothed_score(rows: list[StrengthObservation], side_kind: str) -> float:
    score = 0.0
    for row in rows:
        hero_score = 1.0 if row.outcome == RatedOutcome.HERO_WIN else 0.0 if row.outcome == RatedOutcome.MONSTER_WIN else 0.5
        score += hero_score if side_kind == "hero" else 1.0 - hero_score
    return (score + 0.5) / (len(rows) + 1.0)


def _active_wall_seconds(responses: Iterable[MatchWorkerResponse]) -> float:
    intervals = sorted(
        (
            datetime.fromisoformat(row.started_at).timestamp(),
            datetime.fromisoformat(row.completed_at).timestamp(),
        )
        for row in responses
    )
    if not intervals:
        return 0.0
    total = 0.0
    start, end = intervals[0]
    for next_start, next_end in intervals[1:]:
        if next_start <= end:
            end = max(end, next_end)
        else:
            total += end - start
            start, end = next_start, next_end
    return total + end - start


def _completion_series(responses: Iterable[MatchWorkerResponse]) -> list[dict[str, object]]:
    rows = sorted(responses, key=lambda row: row.completed_at)
    if not rows:
        return []
    origin = min(datetime.fromisoformat(row.started_at).timestamp() for row in rows)
    return [
        {
            "elapsed_seconds": datetime.fromisoformat(row.completed_at).timestamp() - origin,
            "completed_matches": index,
        }
        for index, row in enumerate(rows, start=1)
    ]


def _distribution(values: list[float]) -> dict[str, float | int]:
    if not values:
        return {"count": 0}
    ordered = sorted(values)
    return {
        "count": len(ordered),
        "min": ordered[0],
        "mean": fmean(ordered),
        "p50": _nearest_rank(ordered, 0.5),
        "p95": _nearest_rank(ordered, 0.95),
        "p99": _nearest_rank(ordered, 0.99),
        "max": ordered[-1],
    }


def _nearest_rank(ordered: list[float], percentile: float) -> float:
    index = max(0, math.ceil(percentile * len(ordered)) - 1)
    return ordered[index]


def _short_hash(payload: object) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return sha256(raw.encode("utf-8")).hexdigest()[:16]
