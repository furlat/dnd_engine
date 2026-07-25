"""Durable evidence contracts for AI validation runs."""

from __future__ import annotations

from pathlib import Path
import random

from ai.evaluation.artifacts import (
    SubjectivityAudit,
    ValidationRunArtifact,
    audit_external_selfplay_subjectivity,
    build_external_selfplay_artifact,
    write_validation_run_artifact,
)
from ai.external_selfplay import ExternalSelfPlayResult, ExternalSelfPlayTrace, run_external_selfplay


def test_external_selfplay_artifact_retains_raw_trace_and_derived_metrics(tmp_path: Path) -> None:
    """One artifact contains provenance, raw commands, and reproducible summaries."""
    result = ExternalSelfPlayResult(
        arena_id="sorcerer_barbarian_duel",
        status="encounter_ended",
        command_count=2,
        elapsed_ms=18.0,
        session_ids_by_faction={"heroes": "hero-session", "monsters": "monster-session"},
        final_round=2,
        final_state="completed",
        final_hp_by_actor={"Sorcerer": 7, "Barbarian": 0},
        traces=[
            _trace(
                0,
                "Sorcerer",
                "heroes",
                "accepted",
                policy_ms=1.0,
                total_ms=4.0,
                deep_diagnostics_enabled=True,
            ),
            _trace(1, "Barbarian", "monsters", "rejected", policy_ms=3.0, total_ms=8.0),
        ],
    )

    artifact = build_external_selfplay_artifact(
        result,
        random_seed=42,
        source_revision="working-tree-test",
        subjectivity=SubjectivityAudit(status="not_run"),
    )
    path = write_validation_run_artifact(artifact, tmp_path)
    loaded = ValidationRunArtifact.model_validate_json(path.read_text(encoding="utf-8"))

    assert path.name == f"{artifact.run_id}.json"
    assert loaded.schema_version == 1
    assert loaded.random_seed == 42
    assert loaded.source_revision == "working-tree-test"
    assert "ai/policy/host.py" in loaded.policy.source_paths
    assert "ai/policy/candidates.py" in loaded.policy.source_paths
    assert "dnd/ai/contracts/semantics.py" in loaded.policy.source_paths
    assert "server/agent_runtime/action_semantics.py" in loaded.policy.source_paths
    assert "dnd/ai/runtime/decision_epoch.py" in loaded.policy.source_paths
    assert loaded.policy.source_hash
    assert loaded.result == result
    assert loaded.command_summary.accepted == 1
    assert loaded.command_summary.rejected == 1
    assert loaded.performance.stages["policy_ms"].count == 2
    assert loaded.performance.stages["policy_ms"].median_ms == 2.0
    assert loaded.performance.stages["total_ms"].max_ms == 8.0
    assert loaded.performance.stages["command_http_ms"].count == 2
    assert loaded.performance.stages["command_http_ms"].max_ms == 2.0
    assert loaded.performance.stages["command_followup_sync_ms"].max_ms == 0.5
    assert loaded.performance.stages["pre_command_sync_ms"].max_ms == 1.0
    assert loaded.performance.stages["pre_command_frame_fetch_ms"].max_ms == 0.25
    assert loaded.performance.stages["followup_frame_fetch_ms"].max_ms == 0.5
    assert loaded.performance.normal_stages["policy_ms"].count == 1
    assert loaded.performance.normal_stages["policy_ms"].p95_ms == 3.0
    assert loaded.performance.normal_stages["total_ms"].max_ms == 8.0
    assert loaded.performance.diagnostic_stages["policy_ms"].count == 1
    assert loaded.performance.diagnostic_stages["policy_ms"].p95_ms == 1.0
    assert loaded.performance.diagnostic_stages["total_ms"].max_ms == 4.0
    assert loaded.subjectivity.status == "not_run"
    assert {participant.name for participant in loaded.participants} == {"Sorcerer", "Barbarian"}


def test_artifact_writer_refuses_to_overwrite_run_evidence(tmp_path: Path) -> None:
    """A run id is immutable once its raw evidence has been persisted."""
    result = ExternalSelfPlayResult(
        arena_id="arena",
        status="encounter_ended",
        command_count=0,
        elapsed_ms=1.0,
        session_ids_by_faction={},
        traces=[],
    )
    artifact = build_external_selfplay_artifact(result, run_id="fixed-run")
    write_validation_run_artifact(artifact, tmp_path)

    try:
        write_validation_run_artifact(artifact, tmp_path)
    except FileExistsError:
        pass
    else:
        raise AssertionError("run evidence was overwritten")


def test_seeded_selfplay_restores_the_callers_random_state() -> None:
    """A reproducible self-play seed does not contaminate later engine work."""
    previous_state = random.getstate()

    result = run_external_selfplay(
        "sorcerer_barbarian_duel",
        max_commands=1,
        random_seed=8675309,
    )

    assert result.command_count == 1
    assert random.getstate() == previous_state


def test_subjectivity_audit_accepts_only_epoch_disclosed_known_targets() -> None:
    """A selected legal row and known target pass the retained disclosure audit."""
    trace = _trace(0, "Sorcerer", "heroes", "accepted", policy_ms=1.0, total_ms=4.0)
    trace = trace.model_copy(update={
        "target_uuid": "enemy",
        "target_position": (2, 0),
        "subjective_known_entity_uuids": [trace.actor_uuid, "enemy"],
        "subjective_known_entity_positions": [(0, 0), (2, 0)],
        "subjective_known_tile_positions": [(0, 0), (1, 0), (2, 0)],
        "subjective_affordance_row_ids": [trace.row_id],
        "subjective_affordance_target_uuids": ["enemy"],
        "subjective_affordance_target_positions": [(2, 0)],
        "audit_authorized_entity_uuids": [trace.actor_uuid, "enemy"],
        "audit_authorized_positions": [(0, 0), (1, 0), (2, 0)],
    })
    result = ExternalSelfPlayResult(
        arena_id="arena",
        status="encounter_ended",
        command_count=1,
        elapsed_ms=1.0,
        session_ids_by_faction={"heroes": "heroes-session"},
        traces=[trace],
    )

    audit = audit_external_selfplay_subjectivity(result)

    assert audit.status == "passed"
    assert audit.violations == []


def test_subjectivity_audit_reports_hidden_target_and_position_leaks() -> None:
    """Evidence fails when a command references data absent from subjective state."""
    trace = _trace(0, "Sorcerer", "heroes", "accepted", policy_ms=1.0, total_ms=4.0)
    trace = trace.model_copy(update={
        "target_uuid": "hidden-enemy",
        "target_position": (9, 9),
        "subjective_known_entity_uuids": [trace.actor_uuid],
        "subjective_known_tile_positions": [(0, 0)],
        "subjective_affordance_row_ids": [trace.row_id],
    })
    result = ExternalSelfPlayResult(
        arena_id="arena",
        status="encounter_ended",
        command_count=1,
        elapsed_ms=1.0,
        session_ids_by_faction={"heroes": "heroes-session"},
        traces=[trace],
    )

    audit = audit_external_selfplay_subjectivity(result)

    assert audit.status == "failed"
    assert any("target UUID was not subjectively known" in violation for violation in audit.violations)
    assert any("target position was not subjectively known" in violation for violation in audit.violations)


def test_subjectivity_audit_accepts_affordance_positions_from_seen_cell_memory() -> None:
    """A remembered cell is local subjective knowledge even without a tile fact."""
    trace = _trace(0, "Wizard", "monsters", "accepted", policy_ms=1.0, total_ms=4.0)
    trace = trace.model_copy(update={
        "subjective_known_entity_uuids": [trace.actor_uuid],
        "subjective_seen_cell_positions": [(3, 8)],
        "subjective_affordance_row_ids": [trace.row_id],
        "subjective_affordance_target_positions": [(3, 8)],
        "audit_authorized_entity_uuids": [trace.actor_uuid],
        "audit_authorized_positions": [(3, 8)],
    })
    result = ExternalSelfPlayResult(
        arena_id="arena",
        status="encounter_ended",
        command_count=1,
        elapsed_ms=1.0,
        session_ids_by_faction={"monsters": "monster-session"},
        traces=[trace],
    )

    audit = audit_external_selfplay_subjectivity(result)

    assert audit.status == "passed"
    assert audit.violations == []


def test_subjectivity_audit_checks_actor_routine_targets() -> None:
    """Policy memory cannot retain an undisclosed object identity or position."""
    trace = _trace(0, "Skeleton", "monsters", "accepted", policy_ms=1.0, total_ms=4.0)
    trace = trace.model_copy(update={
        "routine_id": "routine.approach_open_reassess",
        "routine_step_id": "approach",
        "routine_target_uuid": "hidden-door",
        "routine_target_position": (9, 9),
        "subjective_known_entity_uuids": [trace.actor_uuid],
        "subjective_known_tile_positions": [(0, 0)],
        "subjective_affordance_row_ids": [trace.row_id],
    })
    result = ExternalSelfPlayResult(
        arena_id="arena",
        status="encounter_ended",
        command_count=1,
        elapsed_ms=1.0,
        session_ids_by_faction={"monsters": "monster-session"},
        traces=[trace],
    )

    audit = audit_external_selfplay_subjectivity(result)

    assert audit.status == "failed"
    assert any("routine_target UUID was not subjectively known" in violation for violation in audit.violations)
    assert any("routine_target position was not subjectively known" in violation for violation in audit.violations)


def _trace(
    command_index: int,
    actor_name: str,
    actor_faction: str,
    status: str,
    *,
    policy_ms: float,
    total_ms: float,
    deep_diagnostics_enabled: bool = False,
) -> ExternalSelfPlayTrace:
    """Build one compact raw command trace for artifact tests."""
    return ExternalSelfPlayTrace(
        command_index=command_index,
        round_number=1,
        turn_index=command_index,
        session_id=f"{actor_faction}-session",
        actor_uuid=f"actor-{command_index}",
        actor_name=actor_name,
        actor_faction=actor_faction,
        entity_action_count=1,
        position_action_count=1,
        command_type="execute",
        row_id=f"row-{command_index}",
        template_name="Attack",
        reason="test",
        command_status=status,
        deep_diagnostics_enabled=deep_diagnostics_enabled,
        policy_ms=policy_ms,
        command_http_ms=2.0,
        command_followup_sync_ms=0.5,
        pre_command_sync_ms=1.0,
        pre_command_frame_fetch_ms=0.25,
        pre_command_frame_apply_ms=0.1,
        followup_frame_fetch_ms=0.5,
        followup_frame_apply_ms=0.2,
        total_ms=total_ms,
    )
