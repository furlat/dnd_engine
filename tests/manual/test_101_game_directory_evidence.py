"""Focused immutable summary, artifact, and rating-evidence tests."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

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
from dnd.content_system.bootstrap import bootstrap_content_system
from dnd.core.content.durable_characters import CharacterHoldingsRevision
from server.character_settlement import (
    WorkerCharacterHoldingsEvidence,
    build_terminal_settlement_bundle,
)
from server.character_directory_contracts import (
    CharacterLoadoutDraft,
    CreateCharacterRequest,
)
from server.character_directory_service import CharacterDirectoryService
from server.game_directory.contracts import (
    ArtifactCreate,
    ArtifactKind,
    CharacterDeploymentLeaseCreate,
    CharacterRevisionHeads,
    GameCreate,
    GameLifecycleState,
    MembershipCapabilities,
    MembershipCreate,
    MembershipRole,
    PinnedCharacterDeploymentCreate,
    PrincipalCreate,
    PrincipalKind,
    ProducerKind,
    WorkerCreate,
    WorkerState,
    WorkerTerminalReadyManifestCreate,
    WorkerTransportKind,
)
from server.game_directory.errors import (
    ConflictError,
    ImmutableRecordError,
    NotFoundError,
)
from server.game_directory.repository import GameDirectoryRepository
from server.game_summary_store import WorkerSummaryEvidence
from server.worker_terminal_spool import (
    WorkerCharacterHoldingsEvidenceSet,
)

NOW = datetime(2026, 7, 21, 19, 0, tzinfo=UTC)
STARTED = datetime(2026, 7, 21, 18, 58, tzinfo=UTC)
PEPPER = b"summary-test-pepper"


def _open(path: Path) -> GameDirectoryRepository:
    """Open a deterministic repository for evidence tests."""

    return GameDirectoryRepository(path, capability_pepper=PEPPER, clock=lambda: NOW)


def _create_game(repository: GameDirectoryRepository) -> UUID:
    """Create the minimum durable identity needed for a final summary."""

    principal = repository.create_principal(
        PrincipalCreate(principal_kind=PrincipalKind.SERVICE, display_name="Evaluator")
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


def test_hosted_terminal_settles_pinned_character_holdings(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Hosted adoption atomically settles holdings, evidence, and its lease."""

    repository = _open(tmp_path / "directory.sqlite3")
    owner = repository.create_principal(
        PrincipalCreate(
            principal_kind=PrincipalKind.HUMAN,
            display_name="Hosted Owner",
        ),
    )
    worker = repository.create_worker(
        WorkerCreate(
            state=WorkerState.ACTIVE,
            pid=12345,
            process_group_id=12345,
            host_id="test-host",
            transport_kind=WorkerTransportKind.UNIX_SOCKET,
            private_locator="/tmp/test-hosted-terminal.sock",
            protocol_hash="test-protocol",
            engine_version="test-engine",
        ),
    )
    game = repository.create_game(
        GameCreate(
            worker_id=worker.worker_id,
            worker_generation=worker.worker_generation,
            created_by_principal_id=owner.principal_id,
            scenario_kind="evaluation",
            scenario_id="hosted-settlement",
            display_name="Hosted Settlement",
            creation_manifest={"seed": 44},
            seed=44,
            ruleset_version="one-ruleset",
            engine_version="test",
            content_digest="content-v1",
        ),
    )
    game_id = game.game_id
    owner_id = owner.principal_id
    service = CharacterDirectoryService(
        repository,
        bootstrap_content_system(),
    )
    catalog = service.build_creation_catalog()
    plan = next(
        row
        for row in catalog.creation_plans
        if (
            row.source_premade_id
            == "hero.fighter_2_sorcerer_3_spellblade"
        )
    )
    settings = service.ensure_profile_settings(owner_id)
    character = service.create_character(
        owner_id,
        CreateCharacterRequest(
            display_name="Hosted Settlement Proof",
            build=plan.build,
            loadout=CharacterLoadoutDraft(),
            creation_plan_id=plan.plan_id,
            creation_plan_digest=plan.plan_digest,
            expected_content_set_digest=catalog.content_set_digest,
            expected_ruleset_digest=settings.ruleset_digest,
            idempotency_key=uuid4(),
        ),
    ).character
    membership = repository.create_membership(
        MembershipCreate(
            game_id=game_id,
            principal_id=owner_id,
            role=MembershipRole.OWNER,
            capabilities=MembershipCapabilities(
                may_control_entities=True,
            ),
        ),
    )
    lease = repository.acquire_character_deployment_lease(
        CharacterDeploymentLeaseCreate(
            character_id=character.character_id,
            game_id=game_id,
            membership_id=membership.membership_id,
        ),
    )
    runtime_entity_uuid = uuid4()
    deployment = repository.deploy_character_pinned(
        PinnedCharacterDeploymentCreate(
            game_id=game_id,
            membership_id=membership.membership_id,
            character_id=character.character_id,
            entity_uuid=runtime_entity_uuid,
            lease_id=lease.lease_id,
        ),
        expected_character_row_version=character.row_version,
        expected_heads=CharacterRevisionHeads(
            definition_revision=character.current_definition_revision,
            definition_digest=character.current_definition_digest,
            holdings_revision=character.current_holdings_revision,
            holdings_digest=character.current_holdings_digest,
            loadout_revision=character.current_loadout_revision,
            loadout_digest=character.current_loadout_digest,
        ),
    )
    _activate_game(repository, game_id)
    replay, subjective_replay = _terminal_artifacts(game_id)
    summary = _summary(game_id)
    character_snapshot = service.get_character_snapshot(
        owner_id,
        character.character_id,
    )
    resulting_holdings = CharacterHoldingsRevision.create(
        character_id=character.character_id,
        holdings_revision=(
            character_snapshot.holdings.holdings.holdings_revision + 1
        ),
        items=character_snapshot.holdings.holdings.items,
    )
    holdings_evidence = WorkerCharacterHoldingsEvidence(
        game_id=game_id,
        generation_id=UUID(int=404),
        terminal_event_cursor=summary.terminal_cursor.event_cursor,
        terminal_combat_log_cursor=(
            summary.terminal_cursor.combat_log_cursor
        ),
        runtime_entity_uuid=runtime_entity_uuid,
        character_id=character.character_id,
        expected_row_version=character.row_version,
        expected_heads=character_snapshot.heads,
        resulting_holdings=resulting_holdings,
    )
    settlement_bundle = build_terminal_settlement_bundle(
        holdings_evidence,
        deployment,
        settlement_namespace=(
            "dnd-engine:hosted-character-settlement:v1"
        ),
    )
    summary_evidence = WorkerSummaryEvidence(
        generation_id=holdings_evidence.generation_id,
        summary=summary,
        source_event_digest="e" * 64,
        source_combat_log_digest="c" * 64,
    )
    settlement_evidence = WorkerCharacterHoldingsEvidenceSet(
        evidence=(holdings_evidence,),
    ).model_dump(mode="json")
    manifest = repository.stage_worker_terminal_ready_manifest(
        WorkerTerminalReadyManifestCreate(
            game_id=game_id,
            worker_id=worker.worker_id,
            worker_generation=worker.worker_generation,
            objective_artifact=replay,
            subjective_artifact=subjective_replay,
            summary_evidence=summary_evidence.model_dump(mode="json"),
            settlement_evidence=settlement_evidence,
            manifest_digest="d" * 64,
            ready_at=NOW,
        ),
    )
    commit_settlement = repository._commit_terminal_settlement_in_transaction

    def fail_settlement(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("injected hosted settlement failure")

    monkeypatch.setattr(
        repository,
        "_commit_terminal_settlement_in_transaction",
        fail_settlement,
    )
    with pytest.raises(RuntimeError, match="injected hosted settlement failure"):
        repository.finalize_staged_worker_terminal_commit(
            replay,
            summary,
            subjective_artifact=subjective_replay,
            summary_revision=1,
            source_event_digest=summary_evidence.source_event_digest,
            source_combat_log_digest=summary_evidence.source_combat_log_digest,
            manifest_digest=manifest.manifest_digest,
            summary_evidence=summary_evidence.model_dump(mode="json"),
            settlement_evidence=settlement_evidence,
            settlement_bundles=(settlement_bundle,),
            lease_ids=(lease.lease_id,),
        )
    assert repository.get_game(game_id).lifecycle_state is GameLifecycleState.ACTIVE
    assert repository.list_artifacts(game_id) == ()
    with pytest.raises(NotFoundError):
        repository.get_current_summary(game_id)
    with pytest.raises(NotFoundError):
        repository.get_character_settlement_by_deployment(
            deployment.deployment_id,
        )
    assert repository.get_character(character.character_id).current_holdings_revision == 1
    assert len(
        repository.list_character_deployment_leases(
            game_id=game_id,
            active_only=True,
        )
    ) == 1
    assert repository.get_worker_terminal_ready_manifest(game_id).adopted_at is None
    monkeypatch.setattr(
        repository,
        "_commit_terminal_settlement_in_transaction",
        commit_settlement,
    )

    first = repository.finalize_staged_worker_terminal_commit(
        replay,
        summary,
        subjective_artifact=subjective_replay,
        summary_revision=1,
        source_event_digest=summary_evidence.source_event_digest,
        source_combat_log_digest=(
            summary_evidence.source_combat_log_digest
        ),
        manifest_digest=manifest.manifest_digest,
        summary_evidence=summary_evidence.model_dump(mode="json"),
        settlement_evidence=settlement_evidence,
        settlement_bundles=(settlement_bundle,),
        lease_ids=(lease.lease_id,),
    )
    retry = repository.finalize_staged_worker_terminal_commit(
        replay,
        summary,
        subjective_artifact=subjective_replay,
        summary_revision=1,
        source_event_digest=summary_evidence.source_event_digest,
        source_combat_log_digest=(
            summary_evidence.source_combat_log_digest
        ),
        manifest_digest=manifest.manifest_digest,
        summary_evidence=summary_evidence.model_dump(mode="json"),
        settlement_evidence=settlement_evidence,
        settlement_bundles=(settlement_bundle,),
        lease_ids=(lease.lease_id,),
    )

    assert retry == first
    settlement = repository.get_character_settlement_by_deployment(
        deployment.deployment_id,
    )
    assert settlement.resulting_holdings_revision == 2
    assert repository.get_character(character.character_id).current_holdings_revision == 2
    released = repository.list_character_deployment_leases(
        game_id=game_id,
        active_only=False,
    )
    assert len(released) == 1
    assert released[0].released_at is not None
    assert released[0].release_reason == "hosted_game_settled"
    assert repository.get_game(game_id).lifecycle_state is GameLifecycleState.ENDED
    assert repository.get_worker_terminal_ready_manifest(
        game_id,
    ).adopted_at is not None


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
