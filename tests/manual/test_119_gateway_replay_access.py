"""Focused cold authorization and integrity checks for ended-game replay."""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from pathlib import Path
import sqlite3
from uuid import UUID, uuid4

import httpx
import pytest
from fastapi.testclient import TestClient

from dnd.runtime_reset import reset_engine_runtime
from dnd.core.gridmap import get_map
from dnd.entity import Entity
from server.event_stream import event_stream
from server.game_artifact_store import GameArtifactStore
from server.game_directory.canonical import hash_capability
from server.game_directory.contracts import (
    ArtifactKind,
    GameCreate,
    GameLifecycleState,
    MembershipCapabilities,
    MembershipCreate,
    MembershipRole,
    MembershipState,
    PrincipalCreate,
    PrincipalKind,
    ProducerKind,
)
from server.game_directory.repository import GameDirectoryRepository
from server.game_gateway import (
    ENGINE_VERSION,
    GameGatewayService,
    GatewayError,
    create_gateway_app,
)
from server.game_summary_store import WorkerGameSummaryStore, WorkerSummaryEvidence
from server.hosted_worker import HostedWorkerManager
from tests.manual.live_replication_support import create_stream_scene, execute_stream_attack
from server.player_replay_capture import SubjectiveReplayCaptureStore
from server.player_replay import SubjectivePlayerReplayArchive
from server.player_replication.journal import SubjectiveJournalStore
from server.player_replication.runtime import CanonicalSubjectiveReplicationRuntime
from server.replication_perspective import PerspectiveScope
from server.runtime_authority import RuntimeAuthorityCache
from server.subjective_authority import ResolvedSubjectiveAuthority
from server.terminal_evidence import (
    TerminalEvidenceError,
    publish_terminal_evidence,
    validate_terminal_evidence,
)
from server.timeline_contracts import CombatLogProjection
from server.worker_player_replay import build_worker_subjective_replays
from server.worker_replay import build_worker_objective_replay


PEPPER = b"gateway-replay-access-pepper"


@pytest.fixture(autouse=True)
def clean_runtime() -> Iterator[None]:
    event_stream.stop()
    reset_engine_runtime()
    yield
    event_stream.stop()
    reset_engine_runtime()


def _terminal_service(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    membership_state: MembershipState = MembershipState.ACTIVE,
) -> tuple[
    GameGatewayService,
    GameDirectoryRepository,
    GameArtifactStore,
    UUID,
    UUID,
    UUID,
    str,
]:
    capability = "authorized-replay-capability"
    repository = GameDirectoryRepository(
        tmp_path / "directory.sqlite3",
        capability_pepper=PEPPER,
    )
    principal = repository.create_principal(
        PrincipalCreate(
            principal_kind=PrincipalKind.HUMAN,
            display_name="Replay Owner",
            credential_hash=hash_capability(capability, PEPPER),
        )
    )
    artifact_store = GameArtifactStore(tmp_path / "artifacts")
    service = GameGatewayService(
        repository,
        HostedWorkerManager(tmp_path / "runtime"),
        RuntimeAuthorityCache(),
        artifact_store,
        capability_pepper=PEPPER,
    )
    game = repository.create_game(
        GameCreate(
            created_by_principal_id=principal.principal_id,
            scenario_kind="test",
            scenario_id="replay-access",
            display_name="Replay Access",
            creation_manifest={},
            ruleset_version="test",
            engine_version=ENGINE_VERSION,
            content_digest="test-content",
        )
    )
    repository.transition_game(
        game.game_id,
        expected_row_version=game.row_version,
        lifecycle_state=GameLifecycleState.ACTIVE,
    )
    membership = repository.create_membership(
        MembershipCreate(
            game_id=game.game_id,
            principal_id=principal.principal_id,
            role=MembershipRole.OWNER,
            membership_state=membership_state,
            capabilities=MembershipCapabilities(
                may_observe_subjective_state=True,
                may_view_objective_replay=True,
            ),
        )
    )

    scene = create_stream_scene()
    summary_store = WorkerGameSummaryStore()
    summary_store.bind_directory_game_id(
        scene.encounter.uuid,
        game.game_id,
    )
    summary_store.capture_active_encounter(scene.encounter)
    capture_store = SubjectiveReplayCaptureStore()
    runtime = CanonicalSubjectiveReplicationRuntime(
        store=SubjectiveJournalStore(),
        source_journal=event_stream,
        grid_provider=get_map,
        entities_provider=Entity.get_all_entities,
        encounter_provider=lambda: scene.encounter,
        replay_capture_store=capture_store,
    )
    hero_uuid = str(scene.hero.uuid)
    runtime.bind(
        ResolvedSubjectiveAuthority(
            scope=PerspectiveScope(
                session_id="gateway-replay-session",
                membership_id=str(membership.membership_id),
                authority_epoch=membership.authority_epoch,
                projection=CombatLogProjection.SUBJECTIVE,
                controlled_entity_uuids=(hero_uuid,),
                observer_entity_uuids=(hero_uuid,),
                active_observer_uuid=hero_uuid,
            ),
            perspective_epoch_id="gateway-replay-epoch",
        ),
        encounter=scene.encounter,
    )
    execute_stream_attack(scene.hero, scene.monster, scene.encounter)
    scene.encounter.end_encounter("gateway replay access test")
    evidence = summary_store.get_evidence(game.game_id)
    capture = summary_store.get_replay_capture(game.game_id)
    assert evidence is not None
    assert capture is not None
    replay = build_worker_objective_replay(
        capture,
        encounter=scene.encounter,
        stream=event_stream,
    )
    subjective_replay = build_worker_subjective_replays(
        capture,
        replay_capture_store=capture_store,
    )
    runtime.clear_all()
    runtime.stop()

    publish_terminal_evidence(
        repository=repository,
        artifact_store=artifact_store,
        game_id=game.game_id,
        evidence=evidence,
        objective_replay=replay,
        subjective_replay=subjective_replay,
        known_membership_ids=frozenset({membership.membership_id}),
        producer_kind=ProducerKind.WORKER,
    )
    return (
        service,
        repository,
        artifact_store,
        game.game_id,
        membership.membership_id,
        principal.principal_id,
        capability,
    )


@pytest.mark.parametrize(
    "membership_state",
    [MembershipState.ACTIVE, MembershipState.DISCONNECTED],
)
def test_only_capable_seats_read_integrity_checked_terminal_replay(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    membership_state: MembershipState,
) -> None:
    (
        service,
        repository,
        _store,
        game_id,
        membership_id,
        principal_id,
        capability,
    ) = _terminal_service(tmp_path, monkeypatch, membership_state=membership_state)

    replay = service.get_objective_replay(
        game_id,
        principal_id=principal_id,
        principal_capability=capability,
    )
    assert replay.game_id == str(game_id)
    assert replay.terminal_event_cursor == repository.get_game(game_id).final_event_cursor
    subjective = service.get_subjective_replay(
        game_id,
        membership_id,
        principal_id=principal_id,
        principal_capability=capability,
    )
    assert subjective.game_id == str(game_id)
    assert subjective.membership_id == str(membership_id)
    asyncio.run(service.close())
    repository.close()


def test_public_visibility_does_not_grant_replay_and_corruption_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (
        service,
        repository,
        store,
        game_id,
        membership_id,
        _principal_id,
        _capability,
    ) = _terminal_service(tmp_path, monkeypatch)
    outsider_capability = "outsider-capability"
    outsider = repository.create_principal(
        PrincipalCreate(
            principal_kind=PrincipalKind.HUMAN,
            display_name="Outsider",
            credential_hash=hash_capability(outsider_capability, PEPPER),
        )
    )
    with pytest.raises(GatewayError) as denied:
        service.get_objective_replay(
            game_id,
            principal_id=outsider.principal_id,
            principal_capability=outsider_capability,
        )
    assert denied.value.status_code == 403
    assert denied.value.code == "objective_replay_denied"
    with pytest.raises(GatewayError) as subjective_denied:
        service.get_subjective_replay(
            game_id,
            membership_id,
            principal_id=outsider.principal_id,
            principal_capability=outsider_capability,
        )
    assert subjective_denied.value.status_code == 403
    assert subjective_denied.value.code == "subjective_replay_denied"

    artifact = repository.list_artifacts(
        game_id,
        artifact_kind=ArtifactKind.REPLAY_BUNDLE,
    )[0]
    store.path_for_digest(artifact.content_digest).write_bytes(b"corrupt")
    owner = repository.list_memberships(game_id)[0]
    with pytest.raises(GatewayError) as corrupt:
        service.get_objective_replay(
            game_id,
            principal_id=owner.principal_id,
            principal_capability="authorized-replay-capability",
        )
    assert corrupt.value.status_code == 500
    assert corrupt.value.code == "objective_replay_integrity_failed"

    subjective_artifact = repository.list_artifacts(
        game_id,
        artifact_kind=ArtifactKind.SUBJECTIVE_REPLAY_BUNDLE,
    )[0]
    store.path_for_digest(subjective_artifact.content_digest).write_bytes(b"corrupt")
    with pytest.raises(GatewayError) as subjective_corrupt:
        service.get_subjective_replay(
            game_id,
            membership_id,
            principal_id=owner.principal_id,
            principal_capability="authorized-replay-capability",
        )
    assert subjective_corrupt.value.status_code == 500
    assert subjective_corrupt.value.code == "subjective_replay_integrity_failed"
    asyncio.run(service.close())
    repository.close()


def test_membership_replay_never_falls_back_to_another_seat(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (
        service,
        repository,
        _store,
        game_id,
        membership_id,
        principal_id,
        capability,
    ) = _terminal_service(tmp_path, monkeypatch)
    secondary = repository.create_membership(
        MembershipCreate(
            game_id=game_id,
            principal_id=principal_id,
            role=MembershipRole.OBSERVER,
            membership_state=MembershipState.ACTIVE,
            capabilities=MembershipCapabilities(
                may_observe_subjective_state=True,
            ),
        )
    )

    with pytest.raises(GatewayError) as missing:
        service.get_subjective_replay(
            game_id,
            secondary.membership_id,
            principal_id=principal_id,
            principal_capability=capability,
        )
    assert missing.value.status_code == 404
    assert missing.value.code == "subjective_replay_missing"

    denied_membership = repository.create_membership(
        MembershipCreate(
            game_id=game_id,
            principal_id=principal_id,
            role=MembershipRole.ADMINISTRATOR,
            membership_state=MembershipState.ACTIVE,
            capabilities=MembershipCapabilities(),
        )
    )
    with pytest.raises(GatewayError) as denied:
        service.get_subjective_replay(
            game_id,
            denied_membership.membership_id,
            principal_id=principal_id,
            principal_capability=capability,
        )
    assert denied.value.status_code == 403
    assert denied.value.code == "subjective_replay_denied"

    replay = service.get_subjective_replay(
        game_id,
        membership_id,
        principal_id=principal_id,
        principal_capability=capability,
    )
    assert replay.membership_id == str(membership_id)
    asyncio.run(service.close())
    repository.close()


def test_explicit_replay_routes_return_private_membership_only(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (
        service,
        repository,
        store,
        game_id,
        membership_id,
        principal_id,
        capability,
    ) = _terminal_service(tmp_path, monkeypatch)
    asyncio.run(service.close())
    app = create_gateway_app(
        repository=repository,
        worker_manager=HostedWorkerManager(
            tmp_path / "http-runtime",
            warm_pool_size=0,
        ),
        artifact_store=store,
        authority_cache=RuntimeAuthorityCache(),
        capability_pepper=PEPPER,
    )
    headers = {
        "X-Dnd-Principal-Id": str(principal_id),
        "X-Dnd-Principal-Capability": capability,
    }

    with TestClient(app) as client:
        player_response = client.get(
            f"/games/{game_id}/memberships/{membership_id}/replay",
            headers=headers,
        )
        objective_response = client.get(
            f"/games/{game_id}/diagnostics/objective-replay",
            headers=headers,
        )
        old_response = client.get(f"/games/{game_id}/replay", headers=headers)

    assert player_response.status_code == 200
    assert player_response.headers["cache-control"] == "private, no-store"
    assert player_response.json()["membership_id"] == str(membership_id)
    assert "membership_replays" not in player_response.json()
    assert objective_response.status_code == 200
    assert objective_response.headers["cache-control"] == "private, no-store"
    assert old_response.status_code == 404
    repository.close()


@pytest.mark.parametrize(
    "membership_state",
    [MembershipState.REVOKED, MembershipState.LEFT],
)
def test_revoked_or_left_membership_cannot_read_retained_player_replay(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    membership_state: MembershipState,
) -> None:
    (
        service,
        repository,
        _store,
        game_id,
        membership_id,
        principal_id,
        capability,
    ) = _terminal_service(tmp_path, monkeypatch, membership_state=membership_state)

    with pytest.raises(GatewayError) as denied:
        service.get_subjective_replay(
            game_id,
            membership_id,
            principal_id=principal_id,
            principal_capability=capability,
        )
    assert denied.value.status_code == 403
    assert denied.value.code == "subjective_replay_denied"
    asyncio.run(service.close())
    repository.close()


def test_terminal_poll_waits_for_durable_worker_ready_manifest(
    tmp_path: Path,
) -> None:
    repository = GameDirectoryRepository(
        tmp_path / "directory.sqlite3",
        capability_pepper=PEPPER,
    )
    service = GameGatewayService(
        repository,
        HostedWorkerManager(tmp_path / "runtime"),
        RuntimeAuthorityCache(),
        GameArtifactStore(tmp_path / "artifacts"),
        capability_pepper=PEPPER,
    )
    principal = repository.create_principal(
        PrincipalCreate(
            principal_kind=PrincipalKind.SERVICE,
            display_name="Terminal Poll Fixture",
        )
    )
    game = repository.create_game(
        GameCreate(
            created_by_principal_id=principal.principal_id,
            lifecycle_state=GameLifecycleState.ACTIVE,
            scenario_kind="test",
            scenario_id="terminal-poll",
            display_name="Terminal Poll",
            creation_manifest={},
            ruleset_version="test",
            engine_version=ENGINE_VERSION,
            content_digest="test-content",
        )
    )
    requested_paths: list[str] = []

    async def exercise() -> bool:
        def reject_http(request: httpx.Request) -> httpx.Response:
            requested_paths.append(request.url.path)
            raise AssertionError("durable terminal polling must not call the worker")

        async with httpx.AsyncClient(
            transport=httpx.MockTransport(reject_http),
            base_url="http://worker",
        ) as client:
            return await service._persist_worker_summary_if_ready_under_lock(
                game.game_id,
                client,
            )

    assert asyncio.run(exercise()) is False
    assert requested_paths == []
    asyncio.run(service.close())
    repository.close()


def test_terminal_validator_rejects_subjective_archive_coordinate_and_membership_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (
        service,
        repository,
        _store,
        game_id,
        membership_id,
        principal_id,
        capability,
    ) = _terminal_service(tmp_path, monkeypatch)
    objective = service.get_objective_replay(
        game_id,
        principal_id=principal_id,
        principal_capability=capability,
    )
    summary_record = repository.get_current_summary(game_id)
    evidence = WorkerSummaryEvidence(
        generation_id=UUID(objective.generation_id),
        summary=summary_record.summary,
        source_event_digest=summary_record.source_event_digest,
        source_combat_log_digest=summary_record.source_combat_log_digest,
    )
    archive = service._read_subjective_replay_archive(game_id)

    mismatched_cursor = SubjectivePlayerReplayArchive(
        game_id=str(game_id),
        encounter_uuid=archive.encounter_uuid,
        terminal_source_event_cursor=archive.terminal_source_event_cursor + 1,
        terminal_combat_log_cursor=archive.terminal_combat_log_cursor,
        opened_partition_count=0,
    )
    with pytest.raises(TerminalEvidenceError) as cursor_error:
        validate_terminal_evidence(
            game_id=game_id,
            evidence=evidence,
            objective_replay=objective,
            subjective_replay=mismatched_cursor,
            known_membership_ids=frozenset({membership_id}),
        )
    assert cursor_error.value.code == "subjective_replay_cursor_mismatch"

    unknown_membership_id = str(uuid4())
    source_bundle = archive.membership_replays[0]
    unknown_bundle = source_bundle.model_copy(
        update={
            "membership_id": unknown_membership_id,
            "segments": tuple(
                segment.model_copy(
                    update={"membership_id": unknown_membership_id},
                )
                for segment in source_bundle.segments
            ),
        }
    )
    unknown_membership_archive = archive.model_copy(
        update={"membership_replays": (unknown_bundle,)},
    )
    with pytest.raises(TerminalEvidenceError) as membership_error:
        validate_terminal_evidence(
            game_id=game_id,
            evidence=evidence,
            objective_replay=objective,
            subjective_replay=unknown_membership_archive,
            known_membership_ids=frozenset({membership_id}),
        )
    assert membership_error.value.code == "subjective_replay_membership_mismatch"

    retained = service.get_subjective_replay(
        game_id,
        membership_id,
        principal_id=principal_id,
        principal_capability=capability,
    )
    assert retained.membership_id == str(membership_id)
    asyncio.run(service.close())
    repository.close()


@pytest.mark.parametrize(
    ("metadata_update", "expected_code"),
    [
        (
            "schema_version = 'invalid.subjective-replay-schema'",
            "subjective_replay_metadata_invalid",
        ),
        ("byte_size = byte_size + 1", "subjective_replay_size_mismatch"),
    ],
)
def test_subjective_replay_metadata_and_size_fail_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    metadata_update: str,
    expected_code: str,
) -> None:
    (
        service,
        repository,
        _store,
        game_id,
        membership_id,
        principal_id,
        capability,
    ) = _terminal_service(tmp_path, monkeypatch)
    connection = sqlite3.connect(tmp_path / "directory.sqlite3")
    connection.execute(
        f"""
        UPDATE game_artifacts SET {metadata_update}
        WHERE game_id = ? AND artifact_kind = ?
        """,
        (str(game_id), ArtifactKind.SUBJECTIVE_REPLAY_BUNDLE.value),
    )
    connection.commit()
    connection.close()

    with pytest.raises(GatewayError) as invalid:
        service.get_subjective_replay(
            game_id,
            membership_id,
            principal_id=principal_id,
            principal_capability=capability,
        )
    assert invalid.value.status_code == 500
    assert invalid.value.code == expected_code
    asyncio.run(service.close())
    repository.close()
