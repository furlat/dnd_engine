"""Resume contracts for the connected configuration pipeline."""

from __future__ import annotations

from pathlib import Path

import pytest

from ai.evaluation.config_ladder.artifact_store import atomic_write_json
from ai.evaluation.config_ladder.cli import _load_or_build_pipeline_inputs
from ai.evaluation.config_ladder.contracts import ConnectedScheduleEntry
from ai.evaluation.config_ladder.experiment import (
    RetainedExperimentEvidence,
    _retained_match_analysis,
    build_default_catalog,
    build_spell_coverage_report,
)


def test_pipeline_resume_reuses_canonical_catalog_and_schedule_timestamps(
    tmp_path: Path,
) -> None:
    experiment_id = "resume-input-contract"
    first_candidate = build_default_catalog(generated_at="2026-07-17T10:00:00+00:00")
    first_catalog, first_path, first_schedule = _load_or_build_pipeline_inputs(
        output_root=tmp_path,
        experiment_id=experiment_id,
        seed=1701,
        candidate_catalog=first_candidate,
        pair_block_limit=2,
    )

    resumed_candidate = build_default_catalog(generated_at="2026-07-17T11:00:00+00:00")
    resumed_catalog, resumed_path, rebuilt_schedule = _load_or_build_pipeline_inputs(
        output_root=tmp_path,
        experiment_id=experiment_id,
        seed=1701,
        candidate_catalog=resumed_candidate,
        pair_block_limit=2,
    )

    assert resumed_path == first_path
    assert resumed_catalog == first_catalog
    assert rebuilt_schedule == first_schedule
    assert rebuilt_schedule.created_at == first_catalog.generated_at

    retained_schedule_path = tmp_path / experiment_id / "schedule.json"
    atomic_write_json(retained_schedule_path, first_schedule, immutable=True)
    _, _, retained_schedule = _load_or_build_pipeline_inputs(
        output_root=tmp_path,
        experiment_id=experiment_id,
        seed=1701,
        candidate_catalog=resumed_candidate,
        pair_block_limit=2,
    )

    assert retained_schedule == first_schedule


def test_retained_analysis_projects_only_authenticated_aggregate_fields() -> None:
    entry = ConnectedScheduleEntry(
        schedule_index=0,
        match_id="match-fast-analysis",
        pair_block_id="block-fast-analysis",
        hero_configuration_id="hero.alpha",
        hero_configuration_hash="hero-hash",
        monster_configuration_id="monsters.beta",
        monster_configuration_hash="monster-hash",
        battlefield_id="battlefield.open",
        battlefield_hash="battlefield-hash",
        deployment_id="neutral.battlefield.open",
        deployment_hash="deployment-hash",
        simulation_seed=17,
        opening_treatment="hero_first",
    )
    artifact = _analysis_artifact(entry)

    retained = _retained_match_analysis(
        artifact,
        expected_entry=entry,
        expected_result_hash="semantic-result",
        expected_subjectivity_status="passed",
        expected_subjectivity_violations=0,
    )

    assert retained.entry == entry
    assert retained.outcome is not None
    assert retained.outcome.value == "hero_win"
    assert retained.eligibility.eligible
    assert retained.adjudication.kind == "natural_end"
    assert retained.command_count == 3
    assert retained.turn_count == 2
    assert retained.elapsed_ms == 12.5
    assert retained.configured_hero_spell_keys == (
        "dnd.spells.evocation.Fireball",
        "dnd.spells.evocation.MagicMissile",
    )
    assert retained.hero_spell_casts == {"dnd.spells.evocation.Fireball": 1}
    assert retained.monster_spell_casts == {}
    assert not hasattr(retained, "run_artifact")

    coverage = build_spell_coverage_report(
        build_default_catalog(generated_at="2026-07-18T14:00:00+00:00"),
        RetainedExperimentEvidence(
            evidences={entry.match_id: retained},
            responses={},
            infrastructure_failures={},
            artifact_bytes=0,
        ),
    )
    assert coverage["implemented_spell_count"] == 109
    assert coverage["configured_spell_count"] == 2
    assert coverage["exercised_spell_count"] == 1
    assert coverage["configured_but_unused_count"] == 1
    assert coverage["implemented_but_unconfigured_count"] == 107

    with pytest.raises(ValueError, match="Semantic result hash mismatch"):
        _retained_match_analysis(
            artifact,
            expected_entry=entry,
            expected_result_hash="different-result",
            expected_subjectivity_status="passed",
            expected_subjectivity_violations=0,
        )


def _analysis_artifact(entry: ConnectedScheduleEntry) -> dict[str, object]:
    traces = [
        {
            "round_number": 1,
            "turn_index": 0,
            "actor_name": "Hero",
            "actor_faction": "heroes",
            "semantic_key": "dnd.spells.evocation.Fireball",
            "command_status": "accepted",
            "action_resolution": "completed",
        },
        {"round_number": 1, "turn_index": 0, "actor_name": "Hero"},
        {"round_number": 1, "turn_index": 1, "actor_name": "Monster"},
    ]
    return {
        "request": {"entry": entry.model_dump(mode="json")},
        "result": {
            "status": "completed",
            "normalized_result_hash": "semantic-result",
            "subjectivity_status": "passed",
            "subjectivity_violation_count": 0,
            "payload": {
                "entry": entry.model_dump(mode="json"),
                "normalized_result": {"semantic_hash": "semantic-result"},
                "outcome": "hero_win",
                "eligibility": {"eligible": True, "reasons": []},
                "adjudication": {
                    "kind": "natural_end",
                    "detail": "Encounter ended.",
                    "no_progress_command_window": None,
                },
                "arena_manifest": {
                    "entity_rosters": {
                        "heroes": [
                            {
                                "action_template_summary": [
                                    {
                                        "category": "spell",
                                        "semantic_key": "dnd.spells.evocation.Fireball",
                                    }
                                ],
                                "inventory_summary": [
                                    {"name": "Wand of Magic Missiles"}
                                ],
                            }
                        ],
                        "monsters": [
                            {
                                "action_template_summary": [],
                                "inventory_summary": [],
                            }
                        ],
                    }
                },
                "run_artifact": {
                    "subjectivity": {"status": "passed", "violations": []},
                    "result": {
                        "command_count": 3,
                        "elapsed_ms": 12.5,
                        "traces": traces,
                    },
                },
            },
        },
    }
