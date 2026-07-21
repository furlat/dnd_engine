"""Command-line pipeline for connected configuration power evaluation."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Sequence

from ai.evaluation.config_ladder.artifact_store import atomic_write_json
from ai.evaluation.config_ladder.artifact_store import read_json_model
from ai.evaluation.config_ladder.catalog_snapshot import (
    CatalogSnapshot,
    load_catalog_snapshot,
    write_catalog_snapshot,
)
from ai.evaluation.config_ladder.contracts import ConnectedRatingSchedule
from ai.evaluation.config_ladder.experiment import (
    ExperimentExecution,
    build_default_catalog,
    build_default_schedule,
    build_experiment_report,
    load_retained_evidence,
    run_scaling_pilots,
    run_schedule_isolated,
    subset_schedule_by_pair_blocks,
    write_experiment_report,
)
from ai.evaluation.config_ladder.scaling import ParallelScalingAnalysis, ScalingPilot
from ai.evaluation.config_ladder.worker_contracts import CoordinatorSummary
from ai.evaluation.config_ladder.worker_contracts import DEFAULT_RATING_MAX_COMMANDS


DEFAULT_OUTPUT_ROOT = Path("/home/tommaso/.cache/dnd_engine/config-ladders")
DEFAULT_SPOOL_ROOT = Path("/home/tommaso/.cache/dnd_engine/config-ladder-spool")
DEFAULT_REPORT_COPY = Path(__file__).resolve().parents[3] / "ai" / "CONFIGURATION_ELO_REPORT.html"


def run_pipeline(arguments: argparse.Namespace) -> dict[str, object]:
    """Run scaling, the connected tournament, statistics, and HTML rendering."""
    generated_at = datetime.now(timezone.utc).isoformat()
    candidate_catalog = build_default_catalog(generated_at=generated_at)
    experiment_id = arguments.experiment_id or _default_experiment_id(
        candidate_catalog.policy_version,
        candidate_catalog.policy_source_hash,
        arguments.seed,
    )
    output_root = arguments.output_root.resolve()
    spool_root = arguments.spool_root.resolve()
    catalog, catalog_path, full_schedule = _load_or_build_pipeline_inputs(
        output_root=output_root,
        experiment_id=experiment_id,
        seed=arguments.seed,
        candidate_catalog=candidate_catalog,
        pair_block_limit=arguments.pair_block_limit,
    )

    scaling = None
    scaling_pilots = ()
    selected_workers = arguments.worker_count
    if not arguments.skip_scaling:
        scaling, scaling_pilots = run_scaling_pilots(
            full_schedule,
            catalog,
            catalog_path,
            output_root=output_root,
            spool_root=spool_root,
            worker_counts=tuple(arguments.scaling_workers),
            pair_block_count=min(
                arguments.pilot_pair_blocks,
                len(full_schedule.entries_by_pair_block()),
            ),
            max_commands=arguments.max_commands,
        )
        selected_workers = scaling.selected_worker_count
        atomic_write_json(
            output_root / f"{experiment_id}-scaling.json",
            {
                "analysis": scaling.model_dump(mode="json"),
                "pilots": [row.model_dump(mode="json") for row in scaling_pilots],
            },
            immutable=False,
        )

    execution = run_schedule_isolated(
        full_schedule,
        catalog,
        catalog_path,
        output_root=output_root,
        spool_root=spool_root,
        worker_count=selected_workers,
        max_commands=arguments.max_commands,
        soft_timeout_seconds=arguments.soft_timeout_seconds,
        hard_timeout_seconds=arguments.hard_timeout_seconds,
        max_infrastructure_attempts=arguments.max_infrastructure_attempts,
    )
    retained = load_retained_evidence(execution)
    report = build_experiment_report(
        full_schedule,
        catalog,
        execution,
        retained,
        scaling=scaling,
        scaling_pilots=scaling_pilots,
        bootstrap_replicates=arguments.bootstrap_replicates,
        bootstrap_seed=arguments.seed,
    )
    report_copy = None if arguments.no_report_copy else arguments.report_copy.resolve()
    report_json, report_html = write_experiment_report(
        report,
        experiment_dir=execution.experiment_dir,
        html_copy_path=report_copy,
    )
    result = {
        "experiment_id": experiment_id,
        "catalog_path": str(catalog_path),
        "experiment_dir": str(execution.experiment_dir),
        "report_json": str(report_json),
        "report_html": str(report_html),
        "report_copy": str(report_copy) if report_copy is not None else None,
        "selected_worker_count": selected_workers,
        "status": report.get("status"),
    }
    print(json.dumps(result, indent=2))
    return result


def _load_or_build_pipeline_inputs(
    *,
    output_root: Path,
    experiment_id: str,
    seed: int,
    candidate_catalog: CatalogSnapshot,
    pair_block_limit: int | None,
) -> tuple[CatalogSnapshot, Path, ConnectedRatingSchedule]:
    """Return canonical catalog and schedule inputs for a new or resumed run.

    The catalog content hash intentionally excludes its generation timestamp.
    Once a catalog snapshot exists, its retained timestamp is therefore the
    canonical creation time for schedules rebuilt during resume. If the main
    experiment already has a schedule, that exact immutable schedule wins.

    Args:
        output_root: Root containing shared inputs and experiment artifacts.
        experiment_id: Stable identity of the requested experiment.
        seed: Simulation seed used to construct a new schedule.
        candidate_catalog: Catalog built from the currently imported source.
        pair_block_limit: Optional complete-pair limit for focused runs.

    Returns:
        The authenticated catalog, its path, and the exact schedule to run.

    Raises:
        ValueError: If retained inputs disagree with the requested experiment.
    """
    inputs_dir = output_root / "inputs"
    catalog_path = inputs_dir / f"catalog-{candidate_catalog.catalog_hash}.json"
    if catalog_path.exists():
        catalog = load_catalog_snapshot(catalog_path)
    else:
        catalog = candidate_catalog
        write_catalog_snapshot(catalog, catalog_path)

    expected_schedule = build_default_schedule(
        catalog,
        experiment_id=experiment_id,
        seeds=(seed,),
        created_at=catalog.generated_at,
    )
    if pair_block_limit is not None:
        expected_schedule = subset_schedule_by_pair_blocks(
            expected_schedule,
            pair_block_count=pair_block_limit,
            experiment_id=experiment_id,
        )

    schedule_path = output_root / experiment_id / "schedule.json"
    if schedule_path.exists():
        schedule = read_json_model(schedule_path, ConnectedRatingSchedule)
        if schedule.experiment_id != experiment_id:
            raise ValueError("Retained schedule has a different experiment id.")
        if schedule.schedule_hash != expected_schedule.schedule_hash:
            raise ValueError("Retained schedule differs from current canonical inputs.")
        return catalog, catalog_path, schedule

    return catalog, catalog_path, expected_schedule


def prepare(arguments: argparse.Namespace) -> dict[str, object]:
    """Write the immutable catalog and complete schedule without executing it."""
    generated_at = datetime.now(timezone.utc).isoformat()
    catalog = build_default_catalog(generated_at=generated_at)
    experiment_id = arguments.experiment_id or _default_experiment_id(
        catalog.policy_version,
        catalog.policy_source_hash,
        arguments.seed,
    )
    schedule = build_default_schedule(
        catalog,
        experiment_id=experiment_id,
        seeds=(arguments.seed,),
        created_at=generated_at,
    )
    output_root = arguments.output_root.resolve()
    catalog_path = output_root / "inputs" / f"catalog-{catalog.catalog_hash}.json"
    schedule_path = output_root / "inputs" / f"schedule-{schedule.schedule_hash}.json"
    write_catalog_snapshot(catalog, catalog_path)
    atomic_write_json(schedule_path, schedule, immutable=False)
    result = {
        "experiment_id": experiment_id,
        "catalog_path": str(catalog_path),
        "schedule_path": str(schedule_path),
        "matches": len(schedule.entries),
        "pair_blocks": len(schedule.entries_by_pair_block()),
        "exclusions": len(schedule.exclusions),
    }
    print(json.dumps(result, indent=2))
    return result


def analyze(arguments: argparse.Namespace) -> dict[str, object]:
    """Regenerate statistics and HTML from retained canonical evidence."""
    output_root = arguments.output_root.resolve()
    experiment_dir = output_root / arguments.experiment_id
    schedule = read_json_model(experiment_dir / "schedule.json", ConnectedRatingSchedule)
    summary = read_json_model(experiment_dir / "summary.json", CoordinatorSummary)
    catalog = load_catalog_snapshot(arguments.catalog_path.resolve())
    execution_path = experiment_dir / "execution.json"
    wall_seconds = 0.0
    if execution_path.exists():
        execution_payload = json.loads(execution_path.read_text(encoding="utf-8"))
        wall_seconds = float(execution_payload.get("wall_seconds", 0.0))
    execution = ExperimentExecution(
        summary=summary,
        experiment_dir=experiment_dir,
        wall_seconds=wall_seconds,
    )
    retained = load_retained_evidence(execution)
    scaling = None
    scaling_pilots: tuple[ScalingPilot, ...] = ()
    if arguments.scaling_path is not None:
        scaling_payload = json.loads(arguments.scaling_path.read_text(encoding="utf-8"))
        scaling = ParallelScalingAnalysis.model_validate(scaling_payload["analysis"])
        scaling_pilots = tuple(
            ScalingPilot.model_validate(row)
            for row in scaling_payload.get("pilots", [])
        )
    report = build_experiment_report(
        schedule,
        catalog,
        execution,
        retained,
        scaling=scaling,
        scaling_pilots=scaling_pilots,
        bootstrap_replicates=arguments.bootstrap_replicates,
        bootstrap_seed=arguments.seed,
    )
    report_copy = None if arguments.no_report_copy else arguments.report_copy.resolve()
    report_json, report_html = write_experiment_report(
        report,
        experiment_dir=experiment_dir,
        html_copy_path=report_copy,
    )
    result = {
        "experiment_id": arguments.experiment_id,
        "report_json": str(report_json),
        "report_html": str(report_html),
        "report_copy": str(report_copy) if report_copy is not None else None,
        "status": report.get("status"),
    }
    print(json.dumps(result, indent=2))
    return result


def build_parser() -> argparse.ArgumentParser:
    """Return the connected-evaluation command parser."""
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    prepare_parser = subparsers.add_parser("prepare", help="Write exact catalog and schedule inputs.")
    _add_identity_options(prepare_parser)
    prepare_parser.set_defaults(handler=prepare)

    analyze_parser = subparsers.add_parser(
        "analyze",
        help="Rebuild estimates and reports from canonical retained evidence.",
    )
    analyze_parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    analyze_parser.add_argument("--experiment-id", required=True)
    analyze_parser.add_argument("--catalog-path", type=Path, required=True)
    analyze_parser.add_argument("--scaling-path", type=Path)
    analyze_parser.add_argument("--bootstrap-replicates", type=int, default=500)
    analyze_parser.add_argument("--seed", type=int, default=20260717)
    analyze_parser.add_argument("--report-copy", type=Path, default=DEFAULT_REPORT_COPY)
    analyze_parser.add_argument("--no-report-copy", action="store_true")
    analyze_parser.set_defaults(handler=analyze)

    pipeline_parser = subparsers.add_parser(
        "pipeline",
        help="Run scaling, full tournament, estimation, and the offline report.",
    )
    _add_identity_options(pipeline_parser)
    pipeline_parser.add_argument("--spool-root", type=Path, default=DEFAULT_SPOOL_ROOT)
    pipeline_parser.add_argument("--worker-count", type=int, default=8)
    pipeline_parser.add_argument("--scaling-workers", type=int, nargs="+", default=[1, 4, 8, 12, 16])
    pipeline_parser.add_argument("--pilot-pair-blocks", type=int, default=16)
    pipeline_parser.add_argument("--skip-scaling", action="store_true")
    pipeline_parser.add_argument("--pair-block-limit", type=int)
    pipeline_parser.add_argument(
        "--max-commands",
        type=int,
        default=DEFAULT_RATING_MAX_COMMANDS,
    )
    pipeline_parser.add_argument("--soft-timeout-seconds", type=float, default=120.0)
    pipeline_parser.add_argument("--hard-timeout-seconds", type=float, default=135.0)
    pipeline_parser.add_argument("--max-infrastructure-attempts", type=int, default=2)
    pipeline_parser.add_argument("--bootstrap-replicates", type=int, default=500)
    pipeline_parser.add_argument("--report-copy", type=Path, default=DEFAULT_REPORT_COPY)
    pipeline_parser.add_argument("--no-report-copy", action="store_true")
    pipeline_parser.set_defaults(handler=run_pipeline)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Execute one connected-evaluation command."""
    parser = build_parser()
    arguments = parser.parse_args(argv)
    arguments.handler(arguments)
    return 0


def _add_identity_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--experiment-id")
    parser.add_argument("--seed", type=int, default=20260717)


def _default_experiment_id(policy_version: str, policy_hash: str, seed: int) -> str:
    version = "".join(character if character.isalnum() else "-" for character in policy_version).strip("-")
    return f"connected-{version}-{policy_hash[:8]}-seed-{seed}"
