"""Dashboard projection for retained Elo matrix summaries."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ai.evaluation.elo_contract import EloGauntletSummary
from ai.evaluation.elo_validation import validate_elo_summary


def project_elo_dashboard(summary: EloGauntletSummary) -> dict[str, Any]:
    """Return JSON data consumed by the Elo gauntlet dashboard.

    Args:
        summary: Retained evaluator summary.

    Returns:
        Dashboard-ready dictionary derived only from summary JSON.
    """
    validate_elo_summary(summary)
    return {
        "schema_version": 1,
        "source": {
            "kind": "elo_gauntlet_summary",
            "matrix_id": summary.matrix_id,
            "schedule_hash": summary.schedule_hash,
            "generated_at": summary.generated_at,
        },
        "status": {
            "mode": summary.mode,
            "completion_status": summary.completion_status,
            "gate_status": summary.gate_status,
            "gate_reasons": list(summary.gate_reasons),
            "scheduled_count": summary.scheduled_count,
            "completed_count": summary.completed_count,
            "eligible_count": summary.eligible_count,
            "skipped_rating_count": summary.skipped_rating_count,
            "failed_count": summary.failed_count,
            "pending_count": summary.pending_count,
        },
        "coverage": summary.coverage.model_dump(mode="json"),
        "ledgers": {
            name: {
                "standings": [row.model_dump(mode="json") for row in ledger.standings],
                "rating_series": [row.model_dump(mode="json") for row in ledger.rating_series],
                "eligible_match_count": ledger.eligible_match_count,
                "skipped_match_count": ledger.skipped_match_count,
            }
            for name, ledger in summary.ledgers.items()
        },
        "outcomes": _outcome_rows(summary),
        "failures": list(summary.failure_rows),
        "subjectivity": dict(summary.subjectivity_summary),
        "performance": dict(summary.performance),
        "artifacts": _artifact_rows(summary),
    }


def project_elo_dashboard_from_file(summary_path: Path | str) -> dict[str, Any]:
    """Load a summary file and return its dashboard projection."""
    path = Path(summary_path)
    summary = EloGauntletSummary.model_validate_json(path.read_text(encoding="utf-8"))
    projection = project_elo_dashboard(summary)
    projection["source"]["path"] = str(path)
    return projection


def write_elo_dashboard_projection(
    summary_path: Path | str,
    output_path: Path | str,
) -> dict[str, Any]:
    """Write dashboard projection JSON from a retained summary.

    Args:
        summary_path: Retained Elo gauntlet summary.
        output_path: Destination JSON path.

    Returns:
        Projection written to disk.
    """
    projection = project_elo_dashboard_from_file(summary_path)
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(projection, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    return projection


def _outcome_rows(summary: EloGauntletSummary) -> list[dict[str, Any]]:
    rows = []
    for match in summary.matches:
        base = match.base_record
        rows.append({
            "match_id": match.match_id,
            "match_index": match.match_index,
            "attempt_number": match.attempt_number,
            "arena_id": match.schedule_entry.arena_id,
            "seed": match.schedule_entry.random_seed,
            "side_order": match.schedule_entry.side_order_id,
            "status": base.status if base is not None else match.eligibility.runner_status,
            "outcome": base.outcome if base is not None else "unknown",
            "command_count": base.command_count if base is not None else None,
            "elapsed_ms": base.elapsed_ms if base is not None else None,
            "subjectivity_status": match.eligibility.subjectivity_status,
            "eligible": match.eligibility.rating_eligible,
            "reasons": list(match.eligibility.reasons),
        })
    return rows


def _artifact_rows(summary: EloGauntletSummary) -> list[dict[str, Any]]:
    rows = []
    for match in summary.matches:
        for path in match.artifact_paths:
            rows.append({
                "match_id": match.match_id,
                "match_index": match.match_index,
                "arena_id": match.schedule_entry.arena_id,
                "kind": "raw_run",
                "path": path,
            })
        for path in match.prior_attempt_record_paths:
            rows.append({
                "match_id": match.match_id,
                "match_index": match.match_index,
                "arena_id": match.schedule_entry.arena_id,
                "kind": "prior_match_record",
                "path": path,
            })
    return rows
