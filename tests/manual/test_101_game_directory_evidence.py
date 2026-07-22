"""Focused immutable summary, artifact, and rating-evidence tests."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import pytest

from dnd.analytics import (
    EntitySnapshotV1,
    GameSummaryEvidenceV1,
    GameSummaryV1,
    TerminalCursorV1,
    reduce_game_summary,
)
from dnd.core.events import EncounterEndEvent, EncounterStartEvent, EventPhase
from server.game_directory.contracts import (
    GameCreate,
    PrincipalCreate,
    PrincipalKind,
    RatingAdmissionCreate,
    RatingEstimateCreate,
    RatingRunCreate,
    RatingRunStatus,
)
from server.game_directory.errors import ImmutableRecordError
from server.game_directory.repository import GameDirectoryRepository

NOW = datetime(2026, 7, 21, 19, 0, tzinfo=UTC)
STARTED = datetime(2026, 7, 21, 18, 58, tzinfo=UTC)
PEPPER = b"summary-test-pepper"


def _open(path: Path) -> GameDirectoryRepository:
    """Open a deterministic repository for evidence tests."""

    return GameDirectoryRepository(path, capability_pepper=PEPPER, clock=lambda: NOW)


def _create_game(repository: GameDirectoryRepository) -> UUID:
    """Create the minimum durable identity needed for a final summary."""

    principal = repository.create_principal(
        PrincipalCreate(principal_kind=PrincipalKind.SYSTEM_AI, display_name="Evaluator")
    )
    game = repository.create_game(
        GameCreate(
            created_by_principal_id=principal.principal_id,
            scenario_kind="evaluation",
            scenario_id="duel",
            display_name="Summary Duel",
            creation_manifest={"seed": 44},
            seed=44,
            ruleset_version="one-ruleset",
            engine_version="test",
            content_digest="content-v1",
        )
    )
    return game.game_id


def _summary(game_id: UUID, *, damage: int = 11) -> GameSummaryV1:
    """Build a small but fully typed objective terminal summary."""

    hero_uuid = UUID("00000000-0000-0000-0000-000000000101")
    monster_uuid = UUID("00000000-0000-0000-0000-000000000102")
    encounter_uuid = UUID("00000000-0000-0000-0000-000000000103")
    initial = (
        EntitySnapshotV1(
            entity_uuid=hero_uuid,
            name="Hero",
            side_id="heroes",
            normal_hit_points=18,
            maximum_hit_points=18,
            is_defeated=False,
        ),
        EntitySnapshotV1(
            entity_uuid=monster_uuid,
            name="Monster",
            side_id="monsters",
            normal_hit_points=damage,
            maximum_hit_points=damage,
            is_defeated=False,
        ),
    )
    final = (
        initial[0].model_copy(update={"normal_hit_points": 13}),
        initial[1].model_copy(update={"normal_hit_points": 0, "is_defeated": True}),
    )
    events = (
        EncounterStartEvent(
            source_entity_uuid=encounter_uuid,
            encounter_uuid=encounter_uuid,
            combatant_uuids=[hero_uuid, monster_uuid],
            initiative_order=[hero_uuid, monster_uuid],
            phase=EventPhase.COMPLETION,
            timestamp=STARTED,
            use_register=False,
        ),
        EncounterEndEvent(
            source_entity_uuid=encounter_uuid,
            encounter_uuid=encounter_uuid,
            combatant_uuids=[hero_uuid, monster_uuid],
            reason="faction_eliminated",
            phase=EventPhase.COMPLETION,
            timestamp=NOW,
            use_register=False,
        ),
    )
    return reduce_game_summary(
        game_id=str(game_id),
        encounter_uuid=encounter_uuid,
        initial_entities=initial,
        final_entities=final,
        event_history=events,
        combat_logs=(),
        evidence=GameSummaryEvidenceV1(
            terminal_cursor=TerminalCursorV1(event_cursor=84, combat_log_cursor=39),
        ),
    )


def test_summary_publication_is_atomic_idempotent_and_immutable(tmp_path: Path) -> None:
    """Exact retries are harmless while conflicting revision reuse is rejected."""

    repository = _open(tmp_path / "directory.sqlite3")
    game_id = _create_game(repository)
    payload = _summary(game_id)
    published = repository.publish_final_summary(
        payload,
        summary_revision=1,
        source_event_digest="e" * 64,
        source_combat_log_digest="c" * 64,
    )
    retried = repository.publish_final_summary(
        payload,
        summary_revision=1,
        source_event_digest="e" * 64,
        source_combat_log_digest="c" * 64,
    )

    assert retried == published
    assert published.summary_digest == payload.canonical_sha256
    assert repository.get_current_summary(game_id) == published
    assert repository.get_game(game_id).current_summary_digest == published.summary_digest
    events = repository.list_directory_events(game_id=game_id, limit=100)
    summary_events = [event for event in events if event.event_type == "summary_ready"]
    assert len(summary_events) == 1
    assert summary_events[0].payload["summary_digest"] == published.summary_digest

    with pytest.raises(ImmutableRecordError, match="revision 1"):
        repository.publish_final_summary(
            _summary(game_id, damage=12),
            summary_revision=1,
            source_event_digest="e" * 64,
            source_combat_log_digest="c" * 64,
        )

    corrected_payload = _summary(game_id, damage=12)
    corrected = repository.publish_final_summary(
        corrected_payload,
        summary_revision=2,
        source_event_digest="f" * 64,
        source_combat_log_digest="d" * 64,
        supersedes_summary_id=published.summary_id,
    )
    revisions = repository.list_summaries(game_id)
    assert revisions == (published.model_copy(update={"is_current": False}), corrected)
    assert repository.get_current_summary(game_id) == corrected
    repository.close()


def test_rating_runs_reference_exact_immutable_summary_evidence_and_survive_restart(
    tmp_path: Path,
) -> None:
    """Ratings remain derived runs over exact summary digests."""

    database_path = tmp_path / "directory.sqlite3"
    repository = _open(database_path)
    game_id = _create_game(repository)
    summary = repository.publish_final_summary(
        _summary(game_id),
        summary_revision=1,
        source_event_digest="1" * 64,
        source_combat_log_digest="2" * 64,
    )
    run = repository.create_rating_run(
        RatingRunCreate(
            algorithm_id="elo",
            algorithm_version="1",
            parameters={"initial": 1500, "k": 24},
            selection_query={"execution_kind": "evaluation"},
            compatibility_constraints={"ruleset_version": "one-ruleset"},
        )
    )
    admission = repository.add_rating_admission(
        RatingAdmissionCreate(
            rating_run_id=run.rating_run_id,
            game_id=game_id,
            summary_digest=summary.summary_digest,
            admitted=True,
            treatment_id="baseline-policy",
            configuration_id="hero-config-a",
            weight=1.0,
        )
    )
    estimate = repository.publish_rating_estimate(
        RatingEstimateCreate(
            rating_run_id=run.rating_run_id,
            subject_id="hero-config-a",
            estimate=1532.5,
            uncertainty=21.0,
            games=12,
            wins=8,
            losses=3,
            draws=1,
            rank=1,
            diagnostics={"converged": True},
        )
    )
    completed = repository.set_rating_run_status(
        run.rating_run_id,
        status=RatingRunStatus.COMPLETED,
        output_artifact_digest="9" * 64,
    )
    repository.close()

    restarted = _open(database_path)
    assert restarted.get_rating_run(run.rating_run_id) == completed
    assert restarted.list_rating_admissions(run.rating_run_id) == (admission,)
    assert restarted.list_rating_estimates(run.rating_run_id) == (estimate,)

    duplicate = restarted.add_rating_admission(
        RatingAdmissionCreate(
            rating_run_id=run.rating_run_id,
            game_id=game_id,
            summary_digest=summary.summary_digest,
            admitted=True,
            treatment_id="baseline-policy",
            configuration_id="hero-config-a",
            weight=1.0,
        )
    )
    assert duplicate == admission
    restarted.close()
