"""Self-contained connected-rating results report contracts."""

from __future__ import annotations

import json
import re

from ai.evaluation.config_ladder.contracts import (
    ConfigurationStrengthResult,
    ConnectivityReport,
    ContextEffect,
    StrengthDesignDiagnostics,
    StrengthRating,
)
from ai.evaluation.config_ladder.report_projection import build_report_projection
from ai.evaluation.config_ladder.report_renderer import render_report_html


def test_connected_rating_report_is_offline_accessible_and_json_derived() -> None:
    payload = _report_payload(completed_matches=48)

    projection = build_report_projection(payload)
    html = render_report_html(projection)

    assert html.startswith("<!doctype html>")
    assert '<script type="application/json" id="report-data">' in html
    assert '<script src=' not in html
    assert '<link rel="stylesheet"' not in html
    assert "What Was Tested" in html
    assert "Who Was Powerful" in html
    assert "Spell Coverage" in html
    assert "Content Coverage" in html
    assert "How Efficiently It Ran" in html
    assert "What Parallelization Changed" in html
    assert 'role="img"' in html
    assert "<title" in html
    assert "<desc" in html
    assert "<caption" in html
    assert 'scope="col"' in html
    assert 'scope="row"' in html
    assert 'data-source="status.completed_matches" data-value="48"' in html
    assert 'data-source="performance.matches_per_second" data-value="12.5"' in html
    assert 'data-source="spell_coverage.exercised_spell_count" data-value="2"' in html
    assert 'data-source="content_coverage.effected_implemented_identity_count" data-value="2"' in html
    assert "dnd.spells.evocation.Fireball" in html
    assert "Unavailable" in html
    assert "Peak RSS was not retained." in html
    assert 'href="artifacts/match-0048.json.zst"' in html
    assert "sha256:48" in html

    embedded_match = re.search(
        r'<script type="application/json" id="report-data">(.*?)</script>',
        html,
        re.DOTALL,
    )
    assert embedded_match is not None
    assert json.loads(embedded_match.group(1)) == projection

    changed_html = render_report_html(_report_payload(completed_matches=73))
    assert 'data-source="status.completed_matches" data-value="73"' in changed_html
    assert 'data-source="status.completed_matches" data-value="48"' not in changed_html


def test_report_projection_accepts_typed_strength_and_connectivity_models() -> None:
    payload = _report_payload(completed_matches=48)

    projection = build_report_projection(payload)

    assert projection["strength"]["hero_ratings"][0]["configuration_id"] == "hero.alpha"
    assert projection["connectivity"]["component_count"] == 1
    assert projection["source"]["experiment_id"] == "connected-report-test"


def _report_payload(*, completed_matches: int) -> dict[str, object]:
    strength = ConfigurationStrengthResult(
        estimator="Bradley-Terry logistic model",
        converged=True,
        publishable=True,
        regularization=0.25,
        hero_ratings=(
            StrengthRating(
                configuration_id="hero.alpha",
                side_kind="hero",
                coefficient=0.4,
                adjusted_elo=1069.5,
                standard_error=0.1,
                elo_lower_95=1035.2,
                elo_upper_95=1103.8,
                games=24,
            ),
            StrengthRating(
                configuration_id="hero.beta",
                side_kind="hero",
                coefficient=-0.4,
                adjusted_elo=930.5,
                standard_error=0.1,
                elo_lower_95=896.2,
                elo_upper_95=964.8,
                games=24,
            ),
        ),
        monster_ratings=(
            StrengthRating(
                configuration_id="monsters.alpha",
                side_kind="monster_party",
                coefficient=0.2,
                adjusted_elo=1034.7,
                standard_error=0.08,
                elo_lower_95=1007.5,
                elo_upper_95=1061.9,
                games=48,
            ),
        ),
        context_effects=(
            ContextEffect(
                context_kind="opening",
                context_id="hero_first",
                coefficient=0.12,
                elo_equivalent=20.8,
                standard_error=0.04,
            ),
        ),
        design=StrengthDesignDiagnostics(
            connected=True,
            component_count=1,
            rank=6,
            parameter_count=6,
            observation_count=48,
        ),
        log_loss=0.54,
        brier_score=0.18,
        iterations=11,
    )
    connectivity = ConnectivityReport(
        connected=True,
        component_count=1,
        hero_count=2,
        monster_party_count=1,
        edge_count=2,
        component_members=(("hero.alpha", "hero.beta", "monsters.alpha"),),
        degree_by_participant={"hero.alpha": 1, "hero.beta": 1, "monsters.alpha": 2},
    )
    return {
        "schema_version": 1,
        "source": {
            "experiment_id": "connected-report-test",
            "title": "Connected Rating Baseline",
            "generated_at": "2026-07-17T20:00:00+00:00",
            "schedule_hash": "schedule:48",
            "catalog_hash": "catalog:48",
        },
        "status": {
            "phase": "completed",
            "scheduled_matches": 48,
            "completed_matches": completed_matches,
            "eligible_matches": completed_matches,
            "failed_matches": 0,
            "scheduled_pair_blocks": 24,
            "completed_pair_blocks": completed_matches // 2,
        },
        "method": {
            "estimator": "Bradley-Terry logistic model",
            "paired_openings": True,
            "bootstrap": "paired-block bootstrap",
        },
        "quality": {
            "completion": {"status": "passed", "detail": "Every scheduled row completed."},
            "subjectivity": {"status": "passed", "detail": "No witness violations."},
            "determinism": {"status": "passed", "detail": "Serial and parallel canaries matched."},
        },
        "strength_result": strength,
        "connectivity": connectivity,
        "predicted_matchups": {
            "row_ids": ["hero.alpha", "hero.beta"],
            "column_ids": ["monsters.alpha"],
            "cells": [
                {"row_id": "hero.alpha", "column_id": "monsters.alpha", "probability": 0.68, "lower_95": 0.59, "upper_95": 0.76},
                {"row_id": "hero.beta", "column_id": "monsters.alpha", "probability": 0.31, "lower_95": 0.23, "upper_95": 0.40},
            ],
        },
        "empirical_matchups": {
            "row_ids": ["hero.alpha", "hero.beta"],
            "column_ids": ["monsters.alpha"],
            "cells": [
                {"row_id": "hero.alpha", "column_id": "monsters.alpha", "probability": 0.67, "wins": 16, "losses": 8, "draws": 0, "games": 24},
                {"row_id": "hero.beta", "column_id": "monsters.alpha", "probability": 0.29, "wins": 7, "losses": 17, "draws": 0, "games": 24},
            ],
        },
        "specialization": [
            {"configuration_id": "hero.alpha", "battlefield_id": "field.open", "residual_elo": 34.0, "games": 12},
            {"configuration_id": "hero.alpha", "battlefield_id": "field.door", "residual_elo": -18.0, "games": 12},
        ],
        "spell_coverage": {
            "implemented_spell_count": 3,
            "configured_spell_count": 2,
            "exercised_spell_count": 2,
            "configured_but_unused_count": 0,
            "implemented_but_unconfigured_count": 1,
            "total_spell_casts": 19,
            "hero_spell_casts": 11,
            "monster_spell_casts": 8,
            "configuration_coverage_pct": 66.67,
            "exercise_coverage_pct": 66.67,
            "configured_exercise_pct": 100.0,
            "configuration_count": 3,
            "match_count": 48,
            "by_level": [
                {"level": 0, "implemented_spells": 1, "configured_spells": 1, "exercised_spells": 1, "casts": 12},
                {"level": 3, "implemented_spells": 2, "configured_spells": 1, "exercised_spells": 1, "casts": 7},
            ],
            "spells": [
                {
                    "spell_name": "Fire Bolt",
                    "semantic_key": "dnd.spells.evocation.FireBolt",
                    "spell_level": 0,
                    "status": "exercised",
                    "cast_count": 12,
                    "hero_cast_count": 8,
                    "monster_cast_count": 4,
                    "configured_configuration_ids": ["hero.alpha"],
                    "casting_configuration_ids": ["hero.alpha"],
                },
                {
                    "spell_name": "Fireball",
                    "semantic_key": "dnd.spells.evocation.Fireball",
                    "spell_level": 3,
                    "status": "exercised",
                    "cast_count": 7,
                    "hero_cast_count": 3,
                    "monster_cast_count": 4,
                    "configured_configuration_ids": ["monsters.alpha"],
                    "casting_configuration_ids": ["monsters.alpha"],
                },
                {
                    "spell_name": "Lightning Bolt",
                    "semantic_key": "dnd.spells.evocation.LightningBolt",
                    "spell_level": 3,
                    "status": "unconfigured",
                    "cast_count": 0,
                    "hero_cast_count": 0,
                    "monster_cast_count": 0,
                    "configured_configuration_ids": [],
                    "casting_configuration_ids": [],
                },
            ],
        },
        "content_coverage": {
            "implemented_identity_count": 7,
            "configured_implemented_identity_count": 4,
            "effected_implemented_identity_count": 2,
            "configured_but_uneffected_count": 2,
            "implemented_but_unconfigured_count": 3,
            "observed_uncatalogued_identity_count": 0,
            "legacy_identity_count": 0,
            "configuration_coverage_pct": 57.14,
            "effect_coverage_pct": 28.57,
            "configured_effect_pct": 50.0,
            "manifest_match_count": completed_matches,
            "affordance_evidence_match_count": completed_matches,
            "lifecycle_evidence_match_count": completed_matches,
            "match_count": completed_matches,
            "configuration_count": 3,
            "by_family": [
                {
                    "content_kind": "reaction",
                    "identity_count": 1,
                    "implemented_count": 1,
                    "configured_count": 1,
                    "opportunity_identity_count": 1,
                    "effected_identity_count": 1,
                    "opportunity_count": 4,
                    "effect_count": 2,
                }
            ],
            "by_subtype": [],
            "event_lifecycle_counts": [],
            "content": [
                {
                    "semantic_key": "reaction.opportunity_attack",
                    "display_name": "Opportunity Attack",
                    "content_kind": "reaction",
                    "subtype": "movement_reaction",
                    "status": "effected",
                    "implemented": True,
                    "identity_quality": "typed",
                    "evidence_lifecycle": "handler_dispatch",
                    "configured_configuration_ids": ["monsters.alpha"],
                    "exposed_configuration_ids": [],
                    "effecting_configuration_ids": [],
                    "exposure_count": 0,
                    "affordable_exposure_count": 0,
                    "resolved_command_count": 0,
                    "hero_resolved_command_count": 0,
                    "monster_resolved_command_count": 0,
                    "handler_opportunity_count": 4,
                    "handler_effect_count": 2,
                    "condition_application_count": 0,
                    "condition_removal_count": 0,
                    "item_consumption_count": 0,
                    "effect_count": 2,
                }
            ],
        },
        "performance": {
            "wall_time_ms": 4000.0,
            "matches_per_second": 12.5,
            "turns_per_second": 41.25,
            "cpu_utilization_pct": 76.4,
            "peak_rss_mb": {"value": None, "availability": "unavailable", "unavailable_reason": "Peak RSS was not retained."},
            "phase_timings": [
                {"phase": "simulation", "total_ms": 2400.0, "share_pct": 60.0},
                {"phase": "audit", "total_ms": 800.0, "share_pct": 20.0},
                {"phase": "commit", "total_ms": 800.0, "share_pct": 20.0},
            ],
            "completion_series": [
                {"elapsed_seconds": 1.0, "completed_matches": 12},
                {"elapsed_seconds": 2.0, "completed_matches": 27},
                {"elapsed_seconds": 4.0, "completed_matches": completed_matches},
            ],
        },
        "scaling": {
            "selected_worker_count": 8,
            "selection_reason": "Highest throughput before memory pressure rose.",
            "pilots": [
                {"workers": 1, "wall_time_ms": 32000.0, "throughput_matches_per_second": 1.5, "speedup": 1.0, "parallel_efficiency_pct": 100.0, "peak_rss_mb": 620.0},
                {"workers": 8, "wall_time_ms": 4000.0, "throughput_matches_per_second": 12.5, "speedup": 8.0, "parallel_efficiency_pct": 100.0, "peak_rss_mb": 4100.0},
            ],
        },
        "artifacts": [
            {
                "match_id": "match-0048",
                "kind": "compressed_run",
                "path": "scratch/artifacts/match-0048.json.zst",
                "href": "artifacts/match-0048.json.zst",
                "sha256": "sha256:48",
            }
        ],
        "explanations": {
            "hero_strength": "Intervals are retained 95% model intervals.",
            "scaling": "The ideal line is computed from the serial pilot.",
        },
    }
