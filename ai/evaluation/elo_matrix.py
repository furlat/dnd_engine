"""Deterministic schedule construction for complete Elo matrix gauntlets."""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
from typing import Optional
from uuid import uuid4

from ai.evaluation.elo_contract import EloMatrixMode, EloMatrixSchedule, EloMatrixScheduleEntry
from ai.policy.source import CONTROLLER_PROFILE, POLICY_VERSION
from dnd.scenarios.ai_validation_arenas import ValidationArenaSpec, list_ai_validation_arena_specs


DEFAULT_ELO_MATRIX_SEEDS: tuple[int, ...] = tuple(range(1, 11))
DEFAULT_ELO_MATRIX_LARGE_SEEDS: tuple[int, ...] = tuple(range(1, 31))
DEFAULT_ELO_SMOKE_SEEDS: tuple[int, ...] = (1,)
DEFAULT_SIDE_ORDERS: tuple[bool, ...] = (True, False)


def build_elo_matrix_schedule(
    *,
    mode: EloMatrixMode = "elo_matrix",
    arena_ids: Optional[list[str]] = None,
    seeds: Optional[list[int]] = None,
    side_orders: tuple[bool, ...] = DEFAULT_SIDE_ORDERS,
    controller_profile: str = CONTROLLER_PROFILE,
    policy_version: Optional[str] = None,
) -> EloMatrixSchedule:
    """Build a deterministic complete Elo evaluator schedule.

    Args:
        mode: Matrix size mode.
        arena_ids: Optional explicit arena id subset.
        seeds: Optional explicit random seeds.
        side_orders: Hero-first values to schedule.
        controller_profile: Controller profile under evaluation.
        policy_version: Optional policy/source version label. The current shared
            policy version is captured when omitted.

    Returns:
        Stable schedule covering all requested dimensions.

    Raises:
        ValueError: If an arena id is unknown, seeds are duplicated, or side
            orders are empty.
    """
    resolved_policy_version = policy_version or POLICY_VERSION
    specs = list_ai_validation_arena_specs()
    selected_specs = _select_specs(specs, arena_ids)
    selected_seeds = tuple(seeds) if seeds is not None else _default_seeds_for_mode(mode)
    _validate_seeds(selected_seeds)
    if not side_orders:
        raise ValueError("side_orders must contain at least one value")

    entries: list[EloMatrixScheduleEntry] = []
    for spec in selected_specs:
        for seed in selected_seeds:
            for hero_first in side_orders:
                side_order_id = _side_order_id(hero_first)
                repeat_key = f"{spec.arena_id}|seed={seed}|side={side_order_id}|controller={controller_profile}"
                entries.append(
                    EloMatrixScheduleEntry(
                        match_index=len(entries),
                        arena_id=spec.arena_id,
                        random_seed=seed,
                        hero_first=hero_first,
                        side_order_id=side_order_id,
                        controller_profile=controller_profile,
                        policy_version=resolved_policy_version,
                        requested_hero_profile=None,
                        requested_monster_profile=None,
                        tags=tuple(dict.fromkeys((*spec.tags, mode, side_order_id))),
                        schedule_group="all_arenas" if arena_ids is None else "explicit_arenas",
                        repeat_key=repeat_key,
                    )
                )
    _validate_repeat_keys(entries)
    arena_catalog_hash = _arena_catalog_hash(specs)
    policy_catalog_hash = _policy_catalog_hash(controller_profile, resolved_policy_version)
    schedule = EloMatrixSchedule(
        matrix_id=_new_matrix_id(mode),
        mode=mode,
        created_at=_utc_now(),
        arena_catalog_hash=arena_catalog_hash,
        policy_catalog_hash=policy_catalog_hash,
        seed_policy=_seed_policy(mode, selected_seeds),
        side_order_policy=_side_order_policy(side_orders),
        entries=entries,
        schedule_hash="",
    )
    return schedule.model_copy(update={"schedule_hash": _schedule_hash(schedule)})


def expected_row_count(
    *,
    arena_count: int,
    seed_count: int,
    side_order_count: int = len(DEFAULT_SIDE_ORDERS),
) -> int:
    """Return the Cartesian row count for one matrix shape."""
    return arena_count * seed_count * side_order_count


def _select_specs(
    specs: tuple[ValidationArenaSpec, ...],
    arena_ids: Optional[list[str]],
) -> tuple[ValidationArenaSpec, ...]:
    if arena_ids is None:
        return specs
    by_id = {spec.arena_id: spec for spec in specs}
    missing = sorted(set(arena_ids) - set(by_id))
    if missing:
        valid = ", ".join(sorted(by_id))
        raise ValueError(f"Unknown arena ids: {', '.join(missing)}. Valid arena ids: {valid}")
    return tuple(by_id[arena_id] for arena_id in arena_ids)


def _default_seeds_for_mode(mode: EloMatrixMode) -> tuple[int, ...]:
    if mode == "elo_smoke":
        return DEFAULT_ELO_SMOKE_SEEDS
    if mode == "elo_matrix_large":
        return DEFAULT_ELO_MATRIX_LARGE_SEEDS
    return DEFAULT_ELO_MATRIX_SEEDS


def _validate_seeds(seeds: tuple[int, ...]) -> None:
    if not seeds:
        raise ValueError("seeds must contain at least one value")
    if len(set(seeds)) != len(seeds):
        raise ValueError("seeds must be unique")


def _validate_repeat_keys(entries: list[EloMatrixScheduleEntry]) -> None:
    keys = [entry.repeat_key for entry in entries]
    if len(set(keys)) != len(keys):
        raise ValueError("Elo matrix schedule contains duplicate repeat keys")


def _arena_catalog_hash(specs: tuple[ValidationArenaSpec, ...]) -> str:
    payload = [
        {
            "arena_id": spec.arena_id,
            "title": spec.title,
            "hero_role": spec.hero_role,
            "tags": list(spec.tags),
            "expected_pressure": list(spec.expected_pressure),
            "map_notes": list(spec.map_notes),
        }
        for spec in specs
    ]
    return _stable_hash(payload)


def _policy_catalog_hash(controller_profile: str, policy_version: Optional[str]) -> str:
    return _stable_hash({"controller_profile": controller_profile, "policy_version": policy_version})


def _schedule_hash(schedule: EloMatrixSchedule) -> str:
    payload = schedule.model_dump(mode="json", exclude={"matrix_id", "created_at", "schedule_hash"})
    return _stable_hash(payload)


def _stable_hash(payload: object) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return sha256(raw.encode("utf-8")).hexdigest()[:16]


def _seed_policy(mode: EloMatrixMode, seeds: tuple[int, ...]) -> str:
    return f"{mode}:{len(seeds)}:{','.join(str(seed) for seed in seeds)}"


def _side_order_policy(side_orders: tuple[bool, ...]) -> str:
    return ",".join(_side_order_id(value) for value in side_orders)


def _side_order_id(hero_first: bool) -> str:
    return "hero_first" if hero_first else "monster_first"


def _new_matrix_id(mode: EloMatrixMode) -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{timestamp}-ai-{mode}-{uuid4().hex[:8]}"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
