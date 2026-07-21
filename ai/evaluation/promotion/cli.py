"""Command-line workflow for versioned AI policy promotion experiments."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from typing import Sequence

from ai.evaluation.config_ladder.artifact_store import atomic_write_json, read_json_model
from ai.evaluation.config_ladder.worker_contracts import CoordinatorSummary
from ai.evaluation.promotion.catalog_snapshot import (
    PromotionCatalogSnapshot,
    write_promotion_catalog_snapshot,
)
from ai.evaluation.promotion.contracts import PromotionSchedule
from ai.evaluation.promotion.experiment import (
    PromotionExperimentAnalysis,
    analyze_promotion_experiment,
    build_default_promotion_catalog,
    build_default_promotion_schedule,
    build_targeted_promotion_schedule,
    run_promotion_experiment,
)
from ai.evaluation.promotion.report import write_promotion_report
from ai.evaluation.promotion.report_projection import build_promotion_report_projection


def prepare_promotion_experiment(
    *,
    output_root: Path,
    experiment_id: str,
    seeds: tuple[int, ...],
    profile: str = "default",
) -> tuple[Path, PromotionCatalogSnapshot, PromotionSchedule]:
    """Create immutable catalog and schedule files for one promotion attempt."""
    experiment_dir = output_root.resolve() / experiment_id
    experiment_dir.mkdir(parents=True, exist_ok=True)
    catalog_path = experiment_dir / "catalog.json"
    schedule_path = experiment_dir / "schedule.json"
    if catalog_path.exists() or schedule_path.exists():
        if not catalog_path.exists() or not schedule_path.exists():
            raise ValueError("Promotion input directory contains only one of catalog.json and schedule.json.")
        catalog = read_json_model(catalog_path, PromotionCatalogSnapshot)
        schedule = read_json_model(schedule_path, PromotionSchedule)
        if schedule.experiment_id != experiment_id or schedule.catalog_hash != catalog.catalog_hash:
            raise ValueError("Existing promotion inputs do not match the requested experiment identity.")
        return experiment_dir, catalog, schedule

    catalog = build_default_promotion_catalog()
    if profile == "default":
        schedule = build_default_promotion_schedule(
            catalog,
            experiment_id=experiment_id,
            seeds=seeds,
        )
    elif profile == "targeted":
        schedule = build_targeted_promotion_schedule(
            catalog,
            experiment_id=experiment_id,
            seeds=seeds,
        )
    else:
        raise ValueError(f"Unknown promotion profile: {profile}")
    write_promotion_catalog_snapshot(catalog, catalog_path)
    atomic_write_json(schedule_path, schedule, immutable=True)
    return experiment_dir, catalog, schedule


def load_promotion_inputs(
    experiment_dir: Path,
) -> tuple[PromotionCatalogSnapshot, PromotionSchedule]:
    """Load and cross-authenticate prepared promotion inputs."""
    resolved = experiment_dir.resolve()
    catalog = read_json_model(resolved / "catalog.json", PromotionCatalogSnapshot)
    schedule = read_json_model(resolved / "schedule.json", PromotionSchedule)
    if schedule.catalog_hash != catalog.catalog_hash:
        raise ValueError("Promotion schedule and catalog hashes differ.")
    if schedule.experiment_id != resolved.name:
        raise ValueError("Promotion directory name must equal its immutable experiment id.")
    return catalog, schedule


def analyze_prepared_experiment(experiment_dir: Path) -> PromotionExperimentAnalysis:
    """Fit and gate one completed or partially completed prepared experiment."""
    resolved = experiment_dir.resolve()
    _, schedule = load_promotion_inputs(resolved)
    summary = read_json_model(resolved / "summary.json", CoordinatorSummary)
    return analyze_promotion_experiment(
        schedule,
        summary,
        experiment_dir=resolved,
    )


def main(argv: Sequence[str] | None = None) -> int:
    """Prepare, execute, resume, inspect, or analyze a promotion experiment."""
    parser = _build_parser()
    arguments = parser.parse_args(argv)
    if arguments.command == "prepare":
        experiment_dir, catalog, schedule = prepare_promotion_experiment(
            output_root=arguments.output_root,
            experiment_id=arguments.experiment_id,
            seeds=tuple(arguments.seed or (20260718,)),
            profile=arguments.profile,
        )
        print(json.dumps({
            "experiment_dir": str(experiment_dir),
            "catalog_hash": catalog.catalog_hash,
            "schedule_hash": schedule.schedule_hash,
            "matches": len(schedule.entries),
            "comparison_blocks": len(schedule.entries_by_block()),
        }, sort_keys=True))
        return 0
    if arguments.command == "run":
        catalog, schedule = load_promotion_inputs(arguments.experiment_dir)
        summary = asyncio.run(run_promotion_experiment(
            schedule,
            catalog,
            output_root=arguments.experiment_dir.resolve().parent,
            spool_root=arguments.spool_root,
            worker_count=arguments.workers,
            max_commands=arguments.max_commands,
            hard_timeout_seconds=arguments.hard_timeout,
            resume=not arguments.no_resume,
        ))
        print(summary.model_dump_json())
        return 0
    if arguments.command == "status":
        summary = read_json_model(arguments.experiment_dir.resolve() / "summary.json", CoordinatorSummary)
        print(json.dumps({
            "experiment_id": summary.experiment_id,
            "completed": len(summary.records),
            "spawned_workers": summary.spawned_worker_count,
            "resumed_records": summary.resumed_record_count,
            "max_active_workers": summary.max_active_workers,
        }, sort_keys=True))
        return 0
    if arguments.command == "analyze":
        resolved = arguments.experiment_dir.resolve()
        catalog, schedule = load_promotion_inputs(resolved)
        analysis = analyze_prepared_experiment(resolved)
        destination = resolved / "promotion-analysis.json"
        atomic_write_json(destination, analysis, immutable=False)
        projection = build_promotion_report_projection(schedule, catalog, analysis)
        write_promotion_report(
            projection,
            json_path=resolved / "promotion-report.json",
            html_path=resolved / "promotion-report.html",
        )
        print(analysis.model_dump_json())
        return 0
    parser.error(f"Unknown command: {arguments.command}")
    return 2


def _build_parser() -> argparse.ArgumentParser:
    """Build the stable promotion-loop CLI surface."""
    parser = argparse.ArgumentParser(prog="python -m ai.evaluation.promotion")
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare = subparsers.add_parser("prepare", help="Write immutable default catalog and schedule inputs.")
    prepare.add_argument("--output-root", type=Path, required=True)
    prepare.add_argument("--experiment-id", required=True)
    prepare.add_argument("--seed", type=int, action="append")
    prepare.add_argument("--profile", choices=("default", "targeted"), default="default")

    run = subparsers.add_parser("run", help="Run or resume prepared isolated workers.")
    run.add_argument("--experiment-dir", type=Path, required=True)
    run.add_argument("--spool-root", type=Path, required=True)
    run.add_argument(
        "--workers",
        type=_positive_int,
        default=None,
        metavar="N",
        help="Concurrent isolated workers; defaults to 75%% of available logical CPUs.",
    )
    run.add_argument("--max-commands", type=int, default=400)
    run.add_argument("--hard-timeout", type=float, default=135.0)
    run.add_argument("--no-resume", action="store_true")

    status = subparsers.add_parser("status", help="Print canonical coordinator progress.")
    status.add_argument("--experiment-dir", type=Path, required=True)

    analyze = subparsers.add_parser("analyze", help="Fit policy uplift and apply promotion gates.")
    analyze.add_argument("--experiment-dir", type=Path, required=True)
    return parser


def _positive_int(value: str) -> int:
    """Parse a strictly positive command-line integer."""
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("value must be at least one")
    return parsed
