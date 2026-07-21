"""Deterministic four-treatment schedules for policy promotion."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from hashlib import sha256
from itertools import count
from typing import TypeVar

from ai.evaluation.promotion.contracts import (
    MatchupFamily,
    OpeningTreatment,
    PolicyAssignment,
    PromotionMatchupSpec,
    PromotionSchedule,
    PromotionScheduleEntry,
)
from ai.policy.definitions import PolicyGenerationIdentity
from dnd.scenarios.evaluation.models import BattlefieldSpec, DeploymentSpec, SideConfigurationSpec


CatalogRow = TypeVar("CatalogRow")


def build_promotion_schedule(
    *,
    configurations: tuple[SideConfigurationSpec, ...],
    matchups: tuple[PromotionMatchupSpec, ...],
    battlefields: tuple[BattlefieldSpec, ...],
    deployments: tuple[DeploymentSpec, ...],
    seeds: tuple[int, ...],
    candidate: PolicyGenerationIdentity,
    baseline: PolicyGenerationIdentity,
    experiment_id: str,
    catalog_hash: str | None = None,
    created_at: str | None = None,
) -> PromotionSchedule:
    """Expand roster edges into complete policy/opening counterbalances."""
    if candidate.generation_id == baseline.generation_id:
        raise ValueError("Candidate and baseline generation ids must differ.")
    if not configurations or not matchups or not battlefields or not deployments or not seeds:
        raise ValueError("Promotion catalogs, matchups, contexts, and seeds must be non-empty.")
    if len(seeds) != len(set(seeds)):
        raise ValueError("Promotion seeds must be unique.")
    configurations_by_id = _unique_by_id(configurations, "configuration_id")
    deployments_by_id = _unique_by_id(deployments, "deployment_id")
    _unique_by_id(matchups, "matchup_id")
    _unique_by_id(battlefields, "battlefield_id")

    entries: list[PromotionScheduleEntry] = []
    indices = count()
    for seed in seeds:
        for matchup in sorted(matchups, key=lambda row: row.matchup_id):
            side_a = configurations_by_id.get(matchup.side_a_configuration_id)
            side_b = configurations_by_id.get(matchup.side_b_configuration_id)
            if side_a is None or side_b is None:
                raise ValueError(f"Matchup {matchup.matchup_id} references an unknown configuration.")
            _validate_matchup_family(matchup, side_a, side_b)
            for battlefield in sorted(battlefields, key=lambda row: row.battlefield_id):
                if not battlefield.portable:
                    continue
                context_deployments = sorted(
                    (
                        row
                        for row in deployments_by_id.values()
                        if row.battlefield_id == battlefield.battlefield_id
                    ),
                    key=lambda row: row.deployment_id,
                )
                for deployment in context_deployments:
                    if not deployment.portable or not deployment.rating_eligible:
                        continue
                    if len(side_a.members) > len(deployment.hero_slots) or len(side_b.members) > len(deployment.monster_slots):
                        continue
                    block_payload = {
                        "matchup": matchup.matchup_id,
                        "battlefield": battlefield.battlefield_id,
                        "deployment": deployment.deployment_id,
                        "seed": seed,
                        "candidate": candidate.executable_sha256,
                        "baseline": baseline.executable_sha256,
                    }
                    block_id = f"promotion-block-{_short_hash(block_payload)}"
                    treatments: tuple[tuple[OpeningTreatment, PolicyAssignment], ...] = (
                        ("side_a_first", "candidate_a"),
                        ("side_a_first", "candidate_b"),
                        ("side_b_first", "candidate_a"),
                        ("side_b_first", "candidate_b"),
                    )
                    for opening, assignment in treatments:
                        candidate_on_a = assignment == "candidate_a"
                        row_payload = {**block_payload, "opening": opening, "assignment": assignment}
                        entries.append(PromotionScheduleEntry(
                            schedule_index=next(indices),
                            match_id=f"promotion-match-{_short_hash(row_payload)}",
                            comparison_block_id=block_id,
                            matchup_id=matchup.matchup_id,
                            matchup_family=matchup.family,
                            panel=matchup.panel,
                            matchup_tags=matchup.tags,
                            side_a_configuration_id=side_a.configuration_id,
                            side_a_configuration_hash=side_a.mechanical_hash,
                            side_b_configuration_id=side_b.configuration_id,
                            side_b_configuration_hash=side_b.mechanical_hash,
                            side_a_policy_generation_id=(candidate.generation_id if candidate_on_a else baseline.generation_id),
                            side_a_policy_executable_hash=(candidate.executable_sha256 if candidate_on_a else baseline.executable_sha256),
                            side_b_policy_generation_id=(baseline.generation_id if candidate_on_a else candidate.generation_id),
                            side_b_policy_executable_hash=(baseline.executable_sha256 if candidate_on_a else candidate.executable_sha256),
                            candidate_generation_id=candidate.generation_id,
                            baseline_generation_id=baseline.generation_id,
                            battlefield_id=battlefield.battlefield_id,
                            battlefield_hash=battlefield.content_hash,
                            deployment_id=deployment.deployment_id,
                            deployment_hash=deployment.content_hash,
                            simulation_seed=seed,
                            opening_treatment=opening,
                            policy_assignment=assignment,
                        ))
    if not entries:
        raise ValueError("Promotion schedule contains no compatible treatment blocks.")
    _validate_complete_blocks(entries)
    derived_catalog_hash = sha256(json.dumps(
        {
            "configurations": sorted((row.configuration_id, row.mechanical_hash) for row in configurations),
            "battlefields": sorted((row.battlefield_id, row.content_hash) for row in battlefields),
            "deployments": sorted((row.deployment_id, row.content_hash) for row in deployments),
            "candidate": candidate.model_dump(mode="json"),
            "baseline": baseline.model_dump(mode="json"),
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")).hexdigest()
    schedule_hash = sha256(json.dumps(
        [entry.model_dump(mode="json") for entry in entries],
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")).hexdigest()
    return PromotionSchedule(
        experiment_id=experiment_id,
        created_at=created_at or datetime.now(timezone.utc).isoformat(),
        candidate_generation_id=candidate.generation_id,
        baseline_generation_id=baseline.generation_id,
        catalog_hash=catalog_hash or derived_catalog_hash,
        entries=tuple(entries),
        schedule_hash=schedule_hash,
    )


def _validate_complete_blocks(entries: list[PromotionScheduleEntry]) -> None:
    """Require each causal block to contain every policy/opening treatment once."""
    expected = {
        ("side_a_first", "candidate_a"),
        ("side_a_first", "candidate_b"),
        ("side_b_first", "candidate_a"),
        ("side_b_first", "candidate_b"),
    }
    grouped: dict[str, set[tuple[str, str]]] = {}
    for entry in entries:
        grouped.setdefault(entry.comparison_block_id, set()).add(
            (entry.opening_treatment, entry.policy_assignment)
        )
    incomplete = [block_id for block_id, treatments in grouped.items() if treatments != expected]
    if incomplete:
        raise ValueError(f"Incomplete promotion treatment blocks: {sorted(incomplete)}")


def _validate_matchup_family(
    matchup: PromotionMatchupSpec,
    side_a: SideConfigurationSpec,
    side_b: SideConfigurationSpec,
) -> None:
    """Reject mislabeled roster-composition families."""
    if side_a.configuration_id == side_b.configuration_id:
        expected = MatchupFamily.MIRROR
    elif side_a.side_kind == "hero" and side_b.side_kind == "hero":
        expected = MatchupFamily.HERO_VS_HERO
    elif side_a.side_kind == "monster_party" and side_b.side_kind == "monster_party":
        expected = MatchupFamily.MONSTER_VS_MONSTER
    else:
        expected = MatchupFamily.HERO_VS_MONSTER
    if matchup.family != expected:
        raise ValueError(
            f"Matchup {matchup.matchup_id} declares {matchup.family.value}; expected {expected.value}."
        )


def _unique_by_id(rows: tuple[CatalogRow, ...], field_name: str) -> dict[str, CatalogRow]:
    """Index a typed catalog and reject duplicate stable identities."""
    indexed: dict[str, CatalogRow] = {}
    for row in rows:
        key = str(getattr(row, field_name))
        if key in indexed:
            raise ValueError(f"Duplicate {field_name}: {key}")
        indexed[key] = row
    return indexed


def _short_hash(payload: object) -> str:
    """Return a deterministic compact identifier for one schedule input."""
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return sha256(raw.encode("utf-8")).hexdigest()[:16]
