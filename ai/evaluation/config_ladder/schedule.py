"""Deterministic connected schedules for configuration strength experiments."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from hashlib import sha256
from itertools import count

from ai.evaluation.config_ladder.contracts import (
    ConnectedRatingSchedule,
    ConnectedScheduleEntry,
    ConnectivityReport,
    ScheduleExclusion,
)
from dnd.scenarios.evaluation.models import BattlefieldSpec, DeploymentSpec, SideConfigurationSpec


def build_connected_schedule(
    *,
    heroes: tuple[SideConfigurationSpec, ...],
    monster_parties: tuple[SideConfigurationSpec, ...],
    battlefields: tuple[BattlefieldSpec, ...],
    deployments: tuple[DeploymentSpec, ...],
    seeds: tuple[int, ...],
    experiment_id: str | None = None,
    created_at: str | None = None,
) -> ConnectedRatingSchedule:
    """Build a deterministic balanced cross-product with paired openings.

    Args:
        heroes: Rating-eligible hero configurations.
        monster_parties: Rating-eligible monster-party configurations.
        battlefields: Portable battlefield contexts.
        deployments: Spawn formations referenced by battlefields.
        seeds: Unique simulation seeds for every factorial cell.
        experiment_id: Optional caller-provided experiment identifier.
        created_at: Optional fixed timestamp for reproducible fixtures.

    Returns:
        Canonically interleaved connected schedule.

    Raises:
        ValueError: If catalogs are empty, malformed, duplicated, or produce no
            connected eligible rows.
    """
    _validate_catalogs(heroes, monster_parties, battlefields, deployments, seeds)
    deployment_by_id = {row.deployment_id: row for row in deployments}
    blocks: list[tuple[SideConfigurationSpec, SideConfigurationSpec, BattlefieldSpec, DeploymentSpec, int]] = []
    exclusions: list[ScheduleExclusion] = []

    for seed in seeds:
        for battlefield in sorted((row for row in battlefields if row.portable), key=lambda row: row.battlefield_id):
            for deployment_id in battlefield.deployment_ids:
                deployment = deployment_by_id[deployment_id]
                if not deployment.portable or not deployment.rating_eligible:
                    continue
                for offset in range(len(monster_parties)):
                    for hero_index, hero in enumerate(heroes):
                        monsters = monster_parties[(hero_index + offset) % len(monster_parties)]
                        reason = _compatibility_reason(hero, monsters, battlefield, deployment)
                        if reason is not None:
                            exclusions.append(ScheduleExclusion(
                                hero_configuration_id=hero.configuration_id,
                                monster_configuration_id=monsters.configuration_id,
                                battlefield_id=battlefield.battlefield_id,
                                deployment_id=deployment.deployment_id,
                                reason_code=reason[0],
                                message=reason[1],
                            ))
                            continue
                        blocks.append((hero, monsters, battlefield, deployment, seed))

    entries: list[ConnectedScheduleEntry] = []
    indices = count()
    for block_number, (hero, monsters, battlefield, deployment, seed) in enumerate(blocks):
        block_payload = {
            "hero": hero.configuration_id,
            "monsters": monsters.configuration_id,
            "battlefield": battlefield.battlefield_id,
            "deployment": deployment.deployment_id,
            "seed": seed,
        }
        pair_block_id = f"block-{_stable_hash(block_payload)}"
        opening_order = ("hero_first", "monster_first") if block_number % 2 == 0 else ("monster_first", "hero_first")
        for opening_treatment in opening_order:
            schedule_index = next(indices)
            match_payload = {**block_payload, "opening": opening_treatment}
            entries.append(ConnectedScheduleEntry(
                schedule_index=schedule_index,
                match_id=f"match-{_stable_hash(match_payload)}",
                pair_block_id=pair_block_id,
                hero_configuration_id=hero.configuration_id,
                hero_configuration_hash=hero.mechanical_hash,
                monster_configuration_id=monsters.configuration_id,
                monster_configuration_hash=monsters.mechanical_hash,
                battlefield_id=battlefield.battlefield_id,
                battlefield_hash=battlefield.content_hash,
                deployment_id=deployment.deployment_id,
                deployment_hash=deployment.content_hash,
                simulation_seed=seed,
                opening_treatment=opening_treatment,
            ))

    timestamp = created_at or datetime.now(timezone.utc).isoformat()
    catalog_hash = _stable_hash({
        "heroes": [(row.configuration_id, row.mechanical_hash) for row in heroes],
        "monsters": [(row.configuration_id, row.mechanical_hash) for row in monster_parties],
        "battlefields": [(row.battlefield_id, row.content_hash) for row in battlefields],
        "deployments": [(row.deployment_id, row.content_hash) for row in deployments],
    })
    schedule_payload = {
        "catalog_hash": catalog_hash,
        "entries": [row.model_dump(mode="json") for row in entries],
        "exclusions": [row.model_dump(mode="json") for row in exclusions],
    }
    schedule_hash = _stable_hash(schedule_payload)
    schedule = ConnectedRatingSchedule(
        experiment_id=experiment_id or f"config-ladder-{schedule_hash}",
        created_at=timestamp,
        catalog_hash=catalog_hash,
        entries=tuple(entries),
        exclusions=tuple(exclusions),
        schedule_hash=schedule_hash,
    )
    connectivity = schedule_connectivity(schedule)
    if not entries:
        raise ValueError("Connected schedule contains no eligible matches.")
    if not connectivity.connected:
        raise ValueError(f"Rated participant graph is disconnected into {connectivity.component_count} components.")
    return schedule


def schedule_connectivity(schedule: ConnectedRatingSchedule) -> ConnectivityReport:
    """Compute participant graph connectivity and bridge diagnostics."""
    heroes = sorted({entry.hero_configuration_id for entry in schedule.entries})
    monsters = sorted({entry.monster_configuration_id for entry in schedule.entries})
    edges = sorted({(entry.hero_configuration_id, entry.monster_configuration_id) for entry in schedule.entries})
    adjacency: dict[str, set[str]] = {participant: set() for participant in (*heroes, *monsters)}
    for hero_id, monster_id in edges:
        adjacency[hero_id].add(monster_id)
        adjacency[monster_id].add(hero_id)
    components = _components(adjacency)
    bridges = tuple(edge for edge in edges if _is_bridge(adjacency, edge))
    return ConnectivityReport(
        connected=len(components) == 1 and bool(adjacency),
        component_count=len(components),
        hero_count=len(heroes),
        monster_party_count=len(monsters),
        edge_count=len(edges),
        component_members=tuple(tuple(sorted(component)) for component in components),
        degree_by_participant={participant: len(neighbors) for participant, neighbors in sorted(adjacency.items())},
        bridge_edges=bridges,
    )


def _validate_catalogs(
    heroes: tuple[SideConfigurationSpec, ...],
    monster_parties: tuple[SideConfigurationSpec, ...],
    battlefields: tuple[BattlefieldSpec, ...],
    deployments: tuple[DeploymentSpec, ...],
    seeds: tuple[int, ...],
) -> None:
    """Validate schedule catalog references and uniqueness."""
    if not heroes or not monster_parties or not battlefields or not deployments or not seeds:
        raise ValueError("Schedule catalogs and seeds must be non-empty.")
    if any(row.side_kind != "hero" for row in heroes):
        raise ValueError("Hero catalog contains a non-hero configuration.")
    if any(row.side_kind != "monster_party" for row in monster_parties):
        raise ValueError("Monster catalog contains a non-monster-party configuration.")
    if len(seeds) != len(set(seeds)):
        raise ValueError("Simulation seeds must be unique.")
    for label, values in (
        ("hero configuration", [row.configuration_id for row in heroes]),
        ("monster configuration", [row.configuration_id for row in monster_parties]),
        ("battlefield", [row.battlefield_id for row in battlefields]),
        ("deployment", [row.deployment_id for row in deployments]),
    ):
        if len(values) != len(set(values)):
            raise ValueError(f"Duplicate {label} ids are not allowed.")
    deployments_by_id = {row.deployment_id: row for row in deployments}
    for battlefield in battlefields:
        for deployment_id in battlefield.deployment_ids:
            deployment = deployments_by_id.get(deployment_id)
            if deployment is None:
                raise ValueError(f"Battlefield {battlefield.battlefield_id} references unknown deployment {deployment_id}.")
            if deployment.battlefield_id != battlefield.battlefield_id:
                raise ValueError(f"Deployment {deployment_id} belongs to a different battlefield.")


def _compatibility_reason(
    hero: SideConfigurationSpec,
    monsters: SideConfigurationSpec,
    battlefield: BattlefieldSpec,
    deployment: DeploymentSpec,
) -> tuple[str, str] | None:
    """Return a typed incompatibility reason for one factorial cell."""
    if not hero.rating_eligible:
        return "hero_not_rating_eligible", hero.exclusion_reason or "Hero configuration is diagnostic-only."
    if not monsters.rating_eligible:
        return "monster_party_not_rating_eligible", monsters.exclusion_reason or "Monster party is diagnostic-only."
    if len(hero.members) > len(deployment.hero_slots):
        return "insufficient_hero_slots", f"Deployment has {len(deployment.hero_slots)} hero slots for {len(hero.members)} actors."
    if len(monsters.members) > len(deployment.monster_slots):
        return "insufficient_monster_slots", f"Deployment has {len(deployment.monster_slots)} monster slots for {len(monsters.members)} actors."
    if battlefield.battlefield_id != deployment.battlefield_id:
        return "deployment_battlefield_mismatch", "Deployment does not belong to the requested battlefield."
    return None


def _components(adjacency: dict[str, set[str]]) -> list[set[str]]:
    """Return connected components in deterministic order."""
    remaining = set(adjacency)
    components: list[set[str]] = []
    while remaining:
        start = min(remaining)
        stack = [start]
        component: set[str] = set()
        while stack:
            node = stack.pop()
            if node in component:
                continue
            component.add(node)
            stack.extend(sorted(adjacency[node] - component, reverse=True))
        remaining -= component
        components.append(component)
    components.sort(key=lambda rows: tuple(sorted(rows)))
    return components


def _is_bridge(adjacency: dict[str, set[str]], edge: tuple[str, str]) -> bool:
    """Return whether removing one edge increases component count."""
    if not adjacency:
        return False
    before = len(_components(adjacency))
    copied = {node: set(neighbors) for node, neighbors in adjacency.items()}
    left, right = edge
    copied[left].discard(right)
    copied[right].discard(left)
    return len(_components(copied)) > before


def _stable_hash(payload: object) -> str:
    """Return compact hash for deterministic JSON data."""
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return sha256(raw.encode("utf-8")).hexdigest()[:16]
