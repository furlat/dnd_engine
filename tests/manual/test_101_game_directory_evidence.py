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
from dnd.core.life_types import LifeState
from server.game_directory.contracts import (
    ArtifactCreate,
    ArtifactKind,
    GameCreate,
    GameLifecycleState,
    PrincipalCreate,
    PrincipalKind,
    ProducerKind,
    RatingAdmissionCreate,
    RatingEstimateCreate,
    RatingRunCreate,
    RatingRunStatus,
)
from server.game_directory.errors import ConflictError, ImmutableRecordError
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


def _summary(
    game_id: UUID,
    *,
    damage: int = 11,
    terminal_event_cursor: int = 84,
) -> GameSummaryV1:
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
            life_state=LifeState.ALIVE,
            is_defeated=False,
        ),
        EntitySnapshotV1(
            entity_uuid=monster_uuid,
            name="Monster",
            side_id="monsters",
            normal_hit_points=damage,
            maximum_hit_points=damage,
            life_state=LifeState.ALIVE,
            is_defeated=False,
        ),
    )
    final = (
        initial[0].model_copy(update={"normal_hit_points": 13}),
        initial[1].model_copy(
            update={
                "normal_hit_points": 0,
                "life_state": LifeState.DEAD,
                "is_defeated": True,
            }
        ),
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
            terminal_cursor=TerminalCursorV1(
                event_cursor=terminal_event_cursor,
                combat_log_cursor=39,
            ),
        ),
    )


def _terminal_artifacts(
    game_id: UUID,
    *,
    objective_digest: str = "a" * 64,
    subjective_digest: str = "b" * 64,
) -> tuple[ArtifactCreate, ArtifactCreate]:
    """Build the two immutable replay descriptors required at terminal commit."""

    return (
        ArtifactCreate(
            game_id=game_id,
            artifact_kind=ArtifactKind.REPLAY_BUNDLE,
            schema_version="dnd.objective-replay.v1.test",
            media_type="application/json",
            uri=f"file:///immutable/{objective_digest}.objective.json",
            byte_size=123,
            content_digest=objective_digest,
            producer_kind=ProducerKind.WORKER,
            producer_version="test",
        ),
        ArtifactCreate(
            game_id=game_id,
            artifact_kind=ArtifactKind.SUBJECTIVE_REPLAY_BUNDLE,
            schema_version="dnd.subjective-player-replay.v1.test",
            media_type="application/json",
            uri=f"file:///immutable/{subjective_digest}.subjective.json",
            byte_size=321,
            content_digest=subjective_digest,
            producer_kind=ProducerKind.WORKER,
            producer_version="test",
        ),
    )


def _activate_game(repository: GameDirectoryRepository, game_id: UUID) -> None:
    reserved = repository.get_game(game_id)
    repository.transition_game(
        game_id,
        expected_row_version=reserved.row_version,
        lifecycle_state=GameLifecycleState.ACTIVE,
    )


def test_summary_publication_is_atomic_idempotent_and_immutable(tmp_path: Path) -> None:
    """Exact retries are harmless while conflicting revision reuse is rejected."""

    repository = _open(tmp_path / "directory.sqlite3")
    game_id = _create_game(repository)
    _activate_game(repository, game_id)
    payload = _summary(game_id)
    replay, subjective_replay = _terminal_artifacts(game_id)
    _, published = repository.publish_terminal_evidence(
        replay,
        payload,
        additional_artifacts=(subjective_replay,),
        summary_revision=1,
        source_event_digest="e" * 64,
        source_combat_log_digest="c" * 64,
    )
    _, retried = repository.publish_terminal_evidence(
        replay.model_copy(update={"artifact_id": UUID(int=42)}),
        payload,
        additional_artifacts=(
            subjective_replay.model_copy(update={"artifact_id": UUID(int=43)}),
        ),
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

    with pytest.raises(ValueError, match="revision 2"):
        repository.publish_summary_correction(
            _summary(game_id, damage=12),
            summary_revision=1,
            source_event_digest="e" * 64,
            source_combat_log_digest="c" * 64,
        )

    corrected_payload = _summary(game_id, damage=12)
    corrected = repository.publish_summary_correction(
        corrected_payload,
        summary_revision=2,
        source_event_digest="f" * 64,
        source_combat_log_digest="d" * 64,
        supersedes_summary_id=published.summary_id,
    )
    revisions = repository.list_summaries(game_id)
    assert revisions == (published.model_copy(update={"is_current": False}), corrected)
    assert repository.get_current_summary(game_id) == corrected
    with pytest.raises(ImmutableRecordError, match="terminal replay coordinates"):
        repository.publish_summary_correction(
            _summary(game_id, damage=13, terminal_event_cursor=85),
            summary_revision=3,
            source_event_digest="a" * 64,
            source_combat_log_digest="b" * 64,
            supersedes_summary_id=corrected.summary_id,
        )
    repository.close()


def test_rating_runs_reference_exact_immutable_summary_evidence_and_survive_restart(
    tmp_path: Path,
) -> None:
    """Ratings remain derived runs over exact summary digests."""

    database_path = tmp_path / "directory.sqlite3"
    repository = _open(database_path)
    game_id = _create_game(repository)
    _activate_game(repository, game_id)
    replay, subjective_replay = _terminal_artifacts(
        game_id,
        objective_digest="1" * 64,
        subjective_digest="2" * 64,
    )
    _, summary = repository.publish_terminal_evidence(
        replay,
        _summary(game_id),
        additional_artifacts=(subjective_replay,),
        summary_revision=1,
        source_event_digest="3" * 64,
        source_combat_log_digest="4" * 64,
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


def test_terminal_replay_and_summary_publish_as_one_idempotent_transition(
    tmp_path: Path,
) -> None:
    """Ended becomes visible only with immutable replay metadata and summary."""
    repository = _open(tmp_path / "directory.sqlite3")
    game_id = _create_game(repository)
    reserved = repository.get_game(game_id)
    repository.transition_game(
        game_id,
        expected_row_version=reserved.row_version,
        lifecycle_state=GameLifecycleState.ACTIVE,
    )
    replay = ArtifactCreate(
        game_id=game_id,
        artifact_kind=ArtifactKind.REPLAY_BUNDLE,
        schema_version="dnd.objective-replay.v1.test",
        media_type="application/json",
        uri="file:///immutable/replay.json",
        byte_size=123,
        content_digest="a" * 64,
        producer_kind=ProducerKind.WORKER,
        producer_version="test",
    )
    subjective_replay = ArtifactCreate(
        game_id=game_id,
        artifact_kind=ArtifactKind.SUBJECTIVE_REPLAY_BUNDLE,
        schema_version="dnd.subjective-player-replay.v1.test",
        media_type="application/json",
        uri="file:///immutable/subjective-replay.json",
        byte_size=321,
        content_digest="b" * 64,
        producer_kind=ProducerKind.WORKER,
        producer_version="test",
    )
    summary = _summary(game_id)

    first = repository.publish_terminal_evidence(
        replay,
        summary,
        additional_artifacts=(subjective_replay,),
        summary_revision=1,
        source_event_digest="e" * 64,
        source_combat_log_digest="c" * 64,
    )
    retry = repository.publish_terminal_evidence(
        replay.model_copy(update={"artifact_id": UUID(int=42)}),
        summary,
        additional_artifacts=(
            subjective_replay.model_copy(update={"artifact_id": UUID(int=43)}),
        ),
        summary_revision=1,
        source_event_digest="e" * 64,
        source_combat_log_digest="c" * 64,
    )

    assert retry == first
    assert repository.get_game(game_id).lifecycle_state is GameLifecycleState.ENDED
    assert repository.list_artifacts(
        game_id,
        artifact_kind=ArtifactKind.REPLAY_BUNDLE,
    ) == (first[0],)
    assert len(
        repository.list_artifacts(
            game_id,
            artifact_kind=ArtifactKind.SUBJECTIVE_REPLAY_BUNDLE,
        )
    ) == 1
    summary_events = [
        event
        for event in repository.list_directory_events(game_id=game_id, limit=100)
        if event.event_type == "summary_ready"
    ]
    assert len(summary_events) == 1
    assert summary_events[0].payload["replay_digest"] == replay.content_digest
    assert summary_events[0].payload["additional_artifacts"] == [
        {
            "artifact_id": str(subjective_replay.artifact_id),
            "artifact_kind": ArtifactKind.SUBJECTIVE_REPLAY_BUNDLE.value,
            "content_digest": subjective_replay.content_digest,
            "schema_version": subjective_replay.schema_version,
        }
    ]
    with pytest.raises(ConflictError, match="subjective replay evidence"):
        repository.publish_terminal_evidence(
            replay,
            summary,
            summary_revision=1,
            source_event_digest="e" * 64,
            source_combat_log_digest="c" * 64,
        )
    with pytest.raises(ConflictError, match="exact terminal artifact"):
        repository.publish_terminal_evidence(
            replay,
            summary,
            additional_artifacts=(
                subjective_replay.model_copy(
                    update={
                        "content_digest": "d" * 64,
                        "uri": "file:///immutable/changed-subjective-replay.json",
                    }
                ),
            ),
            summary_revision=1,
            source_event_digest="e" * 64,
            source_combat_log_digest="c" * 64,
        )
    repository.close()


def test_terminal_evidence_failure_rolls_back_metadata_and_lifecycle(
    tmp_path: Path,
) -> None:
    """A failed summary insert cannot leave replay metadata or a false ending."""
    repository = _open(tmp_path / "directory.sqlite3")
    game_id = _create_game(repository)
    reserved = repository.get_game(game_id)
    repository.transition_game(
        game_id,
        expected_row_version=reserved.row_version,
        lifecycle_state=GameLifecycleState.ACTIVE,
    )
    replay = ArtifactCreate(
        game_id=game_id,
        artifact_kind=ArtifactKind.REPLAY_BUNDLE,
        schema_version="dnd.objective-replay.v1.test",
        media_type="application/json",
        uri="file:///immutable/replay.json",
        byte_size=123,
        content_digest="b" * 64,
        producer_kind=ProducerKind.WORKER,
        producer_version="test",
    )
    subjective_replay = ArtifactCreate(
        game_id=game_id,
        artifact_kind=ArtifactKind.SUBJECTIVE_REPLAY_BUNDLE,
        schema_version="dnd.subjective-player-replay.v1.test",
        media_type="application/json",
        uri="file:///immutable/subjective-replay.json",
        byte_size=456,
        content_digest="f" * 64,
        producer_kind=ProducerKind.WORKER,
        producer_version="test",
    )

    with pytest.raises(ValueError, match="revision 2"):
        repository.publish_summary_correction(
            _summary(game_id),
            summary_revision=1,
            source_event_digest="e" * 64,
            source_combat_log_digest="c" * 64,
        )
    with pytest.raises(ConflictError, match="terminal replay evidence"):
        repository.publish_summary_correction(
            _summary(game_id),
            summary_revision=2,
            source_event_digest="e" * 64,
            source_combat_log_digest="c" * 64,
            supersedes_summary_id=UUID(int=99),
        )
    with pytest.raises(ValueError, match="subjective replay archive"):
        repository.publish_terminal_evidence(
            replay,
            _summary(game_id),
            summary_revision=1,
            source_event_digest="e" * 64,
            source_combat_log_digest="c" * 64,
        )

    with pytest.raises(ValueError, match="summary_revision"):
        repository.publish_terminal_evidence(
            replay,
            _summary(game_id),
            additional_artifacts=(subjective_replay,),
            summary_revision=0,
            source_event_digest="e" * 64,
            source_combat_log_digest="c" * 64,
        )

    assert repository.list_artifacts(game_id) == ()
    assert repository.get_game(game_id).lifecycle_state is GameLifecycleState.ACTIVE

    active = repository.get_game(game_id)
    repository.transition_game(
        game_id,
        expected_row_version=active.row_version,
        lifecycle_state=GameLifecycleState.INTERRUPTED,
    )
    with pytest.raises(ConflictError, match="only end an active game"):
        repository.publish_terminal_evidence(
            replay,
            _summary(game_id),
            additional_artifacts=(subjective_replay,),
            summary_revision=1,
            source_event_digest="e" * 64,
            source_combat_log_digest="c" * 64,
        )
    assert repository.list_artifacts(game_id) == ()
    assert repository.get_game(game_id).lifecycle_state is GameLifecycleState.INTERRUPTED
    repository.close()
