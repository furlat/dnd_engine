"""Operational preparation contracts for the policy promotion loop."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ai.evaluation.promotion.cli import (
    load_promotion_inputs,
    main,
    prepare_promotion_experiment,
)
from ai.evaluation.promotion.parallelism import (
    recommended_promotion_worker_count,
    resolve_promotion_worker_count,
)


def test_prepare_writes_immutable_reusable_full_field_inputs(tmp_path: Path) -> None:
    """Repeated preparation reuses the exact same catalog and schedule."""
    first_dir, first_catalog, first_schedule = prepare_promotion_experiment(
        output_root=tmp_path,
        experiment_id="candidate-vs-v31",
        seeds=(8801,),
    )
    second_dir, second_catalog, second_schedule = prepare_promotion_experiment(
        output_root=tmp_path,
        experiment_id="candidate-vs-v31",
        seeds=(9999,),
    )
    loaded_catalog, loaded_schedule = load_promotion_inputs(first_dir)

    assert first_dir == second_dir
    assert first_catalog == second_catalog == loaded_catalog
    assert first_schedule == second_schedule == loaded_schedule
    assert (first_dir / "catalog.json").is_file()
    assert (first_dir / "schedule.json").is_file()
    assert len(first_schedule.entries) % 4 == 0
    assert first_schedule.catalog_hash == first_catalog.catalog_hash


def test_prepare_cli_reports_json_derived_counts(tmp_path: Path, capsys) -> None:
    """CLI output reports the retained schedule rather than hand-entered counts."""
    exit_code = main([
        "prepare",
        "--output-root",
        str(tmp_path),
        "--experiment-id",
        "promotion-cli-test",
        "--seed",
        "8802",
    ])
    payload = json.loads(capsys.readouterr().out)
    _, schedule = load_promotion_inputs(tmp_path / "promotion-cli-test")

    assert exit_code == 0
    assert payload["matches"] == len(schedule.entries)
    assert payload["comparison_blocks"] == len(schedule.entries_by_block())
    assert payload["schedule_hash"] == schedule.schedule_hash


def test_promotion_parallelism_uses_most_cpus_with_interactive_headroom() -> None:
    """Automatic promotion concurrency scales with host CPU availability."""
    assert recommended_promotion_worker_count(32) == 24
    assert recommended_promotion_worker_count(16) == 12
    assert recommended_promotion_worker_count(4) == 3
    assert recommended_promotion_worker_count(1) == 1
    assert resolve_promotion_worker_count(30) == 30

    with pytest.raises(ValueError, match="at least one"):
        recommended_promotion_worker_count(0)
    with pytest.raises(ValueError, match="interval"):
        recommended_promotion_worker_count(32, utilization=1.5)
