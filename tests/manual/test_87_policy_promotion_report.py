"""Offline policy-promotion report projection and rendering contracts."""

from __future__ import annotations

import json
from pathlib import Path
import re

import pytest
from pydantic import ValidationError

from ai.evaluation.config_ladder.artifact_store import canonical_json_bytes
from ai.evaluation.promotion.report import (
    PolicyPromotionReportProjection,
    render_promotion_report_html,
    write_promotion_report,
)


def test_report_is_derived_only_from_embedded_canonical_json() -> None:
    """Measured values appear once in JSON and are projected by browser code."""
    projection = _projection()
    html = render_promotion_report_html(projection)
    embedded = _embedded_report(html)
    html_without_payload = re.sub(
        r'<script type="application/json" id="report-data">.*?</script>',
        '<script type="application/json" id="report-data"></script>',
        html,
        flags=re.DOTALL,
    )

    assert embedded == projection.model_dump(mode="json")
    assert "candidate.sentinel.generation" not in html_without_payload
    assert "baseline.sentinel.generation" not in html_without_payload
    assert html.count("Sentinel Candidate 73") == 1
    assert html.count("Sentinel Brute Pair 117") == 1
    assert "999999.25" not in html
    assert 'JSON.parse(document.getElementById("report-data").textContent)' in html
    assert "innerHTML" not in html


def test_report_writes_exact_json_and_self_contained_accessible_html(tmp_path: Path) -> None:
    """JSON and HTML artifacts retain one projection without network dependencies."""
    projection = _projection()
    json_path, html_path = write_promotion_report(
        projection.model_dump(mode="json"),
        json_path=tmp_path / "policy-promotion.json",
        html_path=tmp_path / "policy-promotion.html",
    )
    html = html_path.read_text(encoding="utf-8")

    assert json_path.read_bytes() == canonical_json_bytes(projection, trailing_newline=True)
    assert _embedded_report(html) == json.loads(json_path.read_text(encoding="utf-8"))
    assert '<script type="application/json" id="report-data">' in html
    assert "<script src=" not in html
    assert '<link rel="stylesheet"' not in html
    assert 'href="http' not in html
    assert '<main class="shell" id="main">' in html
    assert '<a class="skip-link" href="#main">' in html
    assert 'role: "img"' in html
    assert 'cell.scope = "col"' in html
    assert 'cell.scope = "row"' in html
    assert 'id="uplift-chart"' in html
    assert 'id="schedule-chart"' in html
    assert 'id="worker-chart"' in html
    assert 'id="timing-chart"' in html
    assert 'id="rate-chart"' in html
    assert 'id="roster-chart"' in html
    assert 'id="catalog-chart"' in html
    assert 'id="effects-chart"' in html
    assert 'renderEloChart("uplift-chart"' in html
    assert 'renderBarChart("schedule-chart"' in html
    assert 'renderBarChart("timing-chart"' in html
    assert 'renderBarChart("rate-chart"' in html


def test_report_projection_rejects_inconsistent_scientific_evidence() -> None:
    """Presentation cannot conceal identity, interval, or schedule inconsistencies."""
    payload = _projection().model_dump(mode="json")
    payload["global_uplift"]["candidate_generation_id"] = "candidate.other"
    with pytest.raises(ValidationError, match="report candidate"):
        PolicyPromotionReportProjection.model_validate(payload)

    payload = _projection().model_dump(mode="json")
    payload["schedule"]["monster_vs_monster"] = 7
    with pytest.raises(ValidationError, match="sum to total_matches"):
        PolicyPromotionReportProjection.model_validate(payload)

    payload = _projection().model_dump(mode="json")
    payload["global_uplift"]["elo_lower_95"] = 40.0
    with pytest.raises(ValidationError, match="inside its confidence interval"):
        PolicyPromotionReportProjection.model_validate(payload)


def _embedded_report(html: str) -> dict[str, object]:
    """Decode the report's inert canonical JSON payload."""
    match = re.search(
        r'<script type="application/json" id="report-data">(.*?)</script>',
        html,
        flags=re.DOTALL,
    )
    assert match is not None
    loaded = json.loads(match.group(1))
    assert isinstance(loaded, dict)
    return loaded


def _projection() -> PolicyPromotionReportProjection:
    """Build one complete report fixture with unmistakable retained values."""
    estimate_identity = {
        "candidate_generation_id": "candidate.sentinel.generation",
        "baseline_generation_id": "baseline.sentinel.generation",
    }
    return PolicyPromotionReportProjection.model_validate({
        "schema_version": 1,
        "source": {
            "experiment_id": "promotion-sentinel-20260718",
            "title": "Policy Promotion: Sentinel Field",
            "generated_at": "2026-07-18T15:45:00+02:00",
            "schedule_hash": "schedule-sha-sentinel-6144",
            "catalog_hash": "catalog-sha-sentinel-384",
        },
        "candidate": {
            "generation_id": "candidate.sentinel.generation",
            "display_name": "Sentinel Candidate 73",
            "version": "2.4.0",
            "executable_sha256": "candidate-executable-sha256-sentinel",
            "controller_profile": "subjective-event-policy-v2",
        },
        "baseline": {
            "generation_id": "baseline.sentinel.generation",
            "display_name": "Sentinel Baseline 29",
            "version": "2.3.0",
            "executable_sha256": "baseline-executable-sha256-sentinel",
            "controller_profile": "subjective-event-policy-v2",
        },
        "decision": {
            "accepted": False,
            "reasons": (
                "global_candidate_uplift_not_credible",
                "credible_slice_regression:matchup_family:hero_vs_hero",
            ),
        },
        "global_uplift": {
            **estimate_identity,
            "elo_delta": 37.25,
            "elo_lower_95": -4.5,
            "elo_upper_95": 79.0,
            "games": 96,
        },
        "slices": (
            {
                "slice_kind": "panel",
                "slice_id": "frozen_core",
                "label": "Frozen core",
                "estimate": {
                    **estimate_identity,
                    "elo_delta": 44.0,
                    "elo_lower_95": 3.0,
                    "elo_upper_95": 85.0,
                    "games": 48,
                },
            },
            {
                "slice_kind": "panel",
                "slice_id": "expanded",
                "label": "Expanded catalog",
                "estimate": {
                    **estimate_identity,
                    "elo_delta": 30.5,
                    "elo_lower_95": -18.0,
                    "elo_upper_95": 79.0,
                    "games": 48,
                },
            },
            {
                "slice_kind": "matchup_family",
                "slice_id": "monster_vs_monster",
                "label": "Monster vs monster",
                "estimate": {
                    **estimate_identity,
                    "elo_delta": 61.0,
                    "elo_lower_95": 8.0,
                    "elo_upper_95": 114.0,
                    "games": 32,
                },
            },
            {
                "slice_kind": "matchup_family",
                "slice_id": "hero_vs_hero",
                "label": "Hero vs hero",
                "estimate": {
                    **estimate_identity,
                    "elo_delta": -22.0,
                    "elo_lower_95": -58.0,
                    "elo_upper_95": -2.0,
                    "games": 16,
                },
            },
        ),
        "roster_strengths": (
            {
                "configuration_id": "hero.sentinel.sorcerer",
                "label": "Sentinel Sorcerer 113",
                "roster_kind": "hero",
                "adjusted_elo": 1086.5,
                "games": 28,
            },
            {
                "configuration_id": "monsters.sentinel.brutes",
                "label": "Sentinel Brute Pair 117",
                "roster_kind": "monster_party",
                "adjusted_elo": 1042.75,
                "games": 34,
            },
            {
                "configuration_id": "hero.sentinel.fighter",
                "label": "Sentinel Fighter 131",
                "roster_kind": "hero",
                "adjusted_elo": 970.25,
                "games": 34,
            },
        ),
        "schedule": {
            "total_matches": 96,
            "comparison_blocks": 24,
            "hero_vs_monster": 48,
            "monster_vs_monster": 24,
            "hero_vs_hero": 16,
            "mirror": 8,
        },
        "workers": {
            "scheduled_matches": 96,
            "completed_matches": 94,
            "eligible_matches": 92,
            "infrastructure_failures": 2,
            "subjectivity_violations": 0,
            "protocol_failures": 1,
            "deterministic_mismatches": 0,
            "content_coverage_regressions": 0,
            "max_active_workers": 12,
        },
        "efficiency": {
            "total_commands": 3187,
            "timings": (
                {"metric_id": "wall_elapsed", "label": "Experiment wall time", "milliseconds": 54321.5},
                {"metric_id": "mean_match", "label": "Mean match", "milliseconds": 812.75},
                {"metric_id": "p95_match", "label": "P95 match", "milliseconds": 1440.25},
                {"metric_id": "epoch_command_p95", "label": "Epoch to command p95", "milliseconds": 4.75},
            ),
            "rates": (
                {"metric_id": "matches_per_second", "label": "Matches", "value": 1.73, "unit": "matches/s"},
                {"metric_id": "commands_per_second", "label": "Commands", "value": 58.67, "unit": "commands/s"},
            ),
        },
        "content": {
            "catalog_counts": (
                {"metric_id": "hero_configurations", "label": "Hero configurations", "value": 20},
                {"metric_id": "monster_configurations", "label": "Monster configurations", "value": 38},
                {"metric_id": "srd_monsters", "label": "SRD monsters", "value": 27},
                {"metric_id": "implemented_identities", "label": "Implemented identities", "value": 384},
                {"metric_id": "configured_identities", "label": "Configured identities", "value": 91},
            ),
            "effect_counts": (
                {"metric_id": "effect_proven", "label": "Effect-proven identities", "value": 48},
                {"metric_id": "handlers_effected", "label": "Handlers effected", "value": 17},
                {"metric_id": "conditions_applied", "label": "Conditions applied", "value": 23},
                {"metric_id": "items_consumed", "label": "Items consumed", "value": 9},
            ),
        },
    })
