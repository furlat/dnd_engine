import pytest
from typer import BadParameter

from ai.evaluation.elo_runner import _parse_side_orders
from ai.evaluation.elo_matrix import build_elo_matrix_schedule, expected_row_count
from ai.policy.source import POLICY_VERSION
from dnd.scenarios.ai_validation_arenas import list_ai_validation_arena_specs


def test_elo_matrix_schedule_covers_every_validation_arena() -> None:
    specs = list_ai_validation_arena_specs()

    schedule = build_elo_matrix_schedule(mode="elo_matrix")

    assert len(schedule.entries) == expected_row_count(
        arena_count=len(specs),
        seed_count=10,
        side_order_count=2,
    )
    assert {entry.arena_id for entry in schedule.entries} == {spec.arena_id for spec in specs}
    assert {entry.side_order_id for entry in schedule.entries} == {"hero_first", "monster_first"}
    assert {entry.random_seed for entry in schedule.entries} == set(range(1, 11))
    assert {entry.policy_version for entry in schedule.entries} == {POLICY_VERSION}


def test_elo_matrix_schedule_hash_is_stable_for_same_inputs() -> None:
    first = build_elo_matrix_schedule(mode="elo_matrix", arena_ids=["standard_skeleton_doors"], seeds=[1, 2])
    second = build_elo_matrix_schedule(mode="elo_matrix", arena_ids=["standard_skeleton_doors"], seeds=[1, 2])
    changed = build_elo_matrix_schedule(mode="elo_matrix", arena_ids=["standard_skeleton_doors"], seeds=[1, 3])

    assert first.schedule_hash == second.schedule_hash
    assert first.schedule_hash != changed.schedule_hash


def test_elo_matrix_schedule_rejects_invalid_inputs() -> None:
    with pytest.raises(ValueError, match="Unknown arena ids"):
        build_elo_matrix_schedule(mode="elo_matrix", arena_ids=["nope"])

    with pytest.raises(ValueError, match="seeds must be unique"):
        build_elo_matrix_schedule(mode="elo_matrix", arena_ids=["standard_skeleton_doors"], seeds=[1, 1])

    with pytest.raises(ValueError, match="side_orders"):
        build_elo_matrix_schedule(mode="elo_matrix", arena_ids=["standard_skeleton_doors"], side_orders=())


def test_cli_side_order_parser_preserves_requested_matrix_dimensions() -> None:
    assert _parse_side_orders(None) == (True, False)
    assert _parse_side_orders(["monster-first"]) == (False,)
    assert _parse_side_orders(["hero_first", "monster_first"]) == (True, False)
    assert _parse_side_orders(["hero-first", "hero_first"]) == (True,)
    with pytest.raises(BadParameter, match="hero-first or monster-first"):
        _parse_side_orders(["coin-flip"])
