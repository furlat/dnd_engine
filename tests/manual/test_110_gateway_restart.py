"""Focused restart reconciliation for the multi-game gateway."""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from pathlib import Path
import sqlite3
from uuid import uuid4

import pytest
from dnd.runtime_reset import reset_engine_runtime
from server.event_stream import event_stream
from server.game_directory.contracts import (
    GameCreate,
    GameLifecycleState,
    PrincipalCreate,
    PrincipalKind,
    WorkerCreate,
    WorkerState,
    WorkerTransportKind,
)
from server.game_directory.repository import GameDirectoryRepository
from server.game_artifact_store import GameArtifactStore
from server.game_gateway import GameGatewayService
from server.hosted_worker import HostedWorkerManager
from server.runtime_authority import RuntimeAuthorityCache
from server.game_summary_store import WorkerGameSummaryStore
from tests.manual.live_replication_support import create_stream_scene, execute_stream_attack
from server.player_replay import SubjectivePlayerReplayArchive
from server.worker_replay import build_worker_objective_replay
from server.worker_terminal_spool import WorkerTerminalSpool


@pytest.fixture(autouse=True)
def clean_runtime() -> Iterator[None]:
    """Keep restart-adoption evidence isolated from retained engine state."""

    event_stream.stop()
    reset_engine_runtime()
    event_stream.ensure_attached()
    yield
    event_stream.stop()
    reset_engine_runtime()


def test_gateway_start_interrupts_active_game_without_owned_worker(tmp_path: Path) -> None:
    """A restarted gateway never advertises an unreachable game as active."""
    repository = GameDirectoryRepository(
        tmp_path / "directory.sqlite3",
        capability_pepper=b"restart-test-pepper",
    )
    principal = repository.create_principal(
        PrincipalCreate(
            principal_kind=PrincipalKind.HUMAN,
            display_name="Restart Owner",
        )
    )
    worker = repository.create_worker(
        WorkerCreate(
            state=WorkerState.ACTIVE,
            pid=999999,
            process_group_id=999999,
            host_id="previous-gateway",
            transport_kind=WorkerTransportKind.UNIX_SOCKET,
            private_locator="/tmp/absent-dnd-worker.sock",
            protocol_hash="test-protocol",
            engine_version="test-engine",
        )
    )
    game = repository.create_game(
        GameCreate(
            worker_id=worker.worker_id,
            worker_generation=worker.worker_generation,
            created_by_principal_id=principal.principal_id,
            lifecycle_state=GameLifecycleState.ACTIVE,
            scenario_kind="preset",
            scenario_id="restart-test",
            display_name="Lost Active Game",
            creation_manifest={"scenario": "restart-test"},
            ruleset_version="test-rules",
            engine_version="test-engine",
            content_digest="test-content",
        )
    )

    service = GameGatewayService(
        repository,
        HostedWorkerManager(tmp_path / "runtime"),
        RuntimeAuthorityCache(),
        GameArtifactStore(tmp_path / "artifacts"),
        capability_pepper=b"restart-test-pepper",
    )

    reconciled_game = repository.get_game(game.game_id)
    reconciled_worker = repository.get_worker(worker.worker_id)
    assert reconciled_game.lifecycle_state is GameLifecycleState.INTERRUPTED
    assert reconciled_game.terminal_reason == "gateway_restart"
    assert reconciled_worker.state is WorkerState.LOST
    assert reconciled_worker.failure_code == "gateway_restart"

    asyncio.run(service.close())
    repository.close()


def test_gateway_directory_has_durable_terminal_ready_manifest(
    tmp_path: Path,
) -> None:
    """Measure the missing restart-adoption record before behavior is added."""

    database_path = tmp_path / "directory.sqlite3"
    repository = GameDirectoryRepository(
        database_path,
        capability_pepper=b"restart-test-pepper",
    )
    repository.close()
    with sqlite3.connect(database_path) as connection:
        columns = connection.execute(
            """
            PRAGMA table_info(worker_terminal_ready_manifests)
            """,
        ).fetchall()
    assert {
        "game_id",
        "worker_generation",
        "objective_artifact_json",
        "subjective_artifact_json",
        "summary_evidence_json",
        "manifest_digest",
        "ready_at",
        "adopted_at",
    }.issubset({row[1] for row in columns})


def test_gateway_restart_adopts_ready_manifest_before_orphan_interrupt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A finished worker is adopted from disk instead of being interrupted."""

    repository = GameDirectoryRepository(
        tmp_path / "directory.sqlite3",
        capability_pepper=b"restart-test-pepper",
    )
    principal = repository.create_principal(
        PrincipalCreate(
            principal_kind=PrincipalKind.SERVICE,
            display_name="Ready Worker",
        ),
    )
    worker = repository.create_worker(
        WorkerCreate(
            state=WorkerState.ACTIVE,
            pid=999998,
            process_group_id=999998,
            host_id="previous-gateway",
            transport_kind=WorkerTransportKind.UNIX_SOCKET,
            private_locator="/tmp/ready-worker.sock",
            protocol_hash="test-protocol",
            engine_version="test-engine",
        ),
    )
    game_id = uuid4()
    game = repository.create_game(
        GameCreate(
            game_id=game_id,
            worker_id=worker.worker_id,
            worker_generation=worker.worker_generation,
            created_by_principal_id=principal.principal_id,
            lifecycle_state=GameLifecycleState.ACTIVE,
            scenario_kind="preset",
            scenario_id="restart-ready",
            display_name="Ready Terminal Game",
            creation_manifest={"scenario": "restart-ready"},
            ruleset_version="test-rules",
            engine_version="test-engine",
            content_digest="test-content",
        ),
    )
    scene = create_stream_scene()
    summary_store = WorkerGameSummaryStore()
    summary_store.bind_directory_game_id(scene.encounter.uuid, game_id)
    summary_store.capture_active_encounter(scene.encounter)
    execute_stream_attack(scene.hero, scene.monster, scene.encounter)
    scene.encounter.end_encounter("restart adoption")
    summary = summary_store.get_evidence(game_id)
    capture = summary_store.get_replay_capture(game_id)
    assert summary is not None
    assert capture is not None
    objective = build_worker_objective_replay(
        capture,
        encounter=scene.encounter,
        stream=event_stream,
    )
    subjective = SubjectivePlayerReplayArchive(
        game_id=str(game_id),
        encounter_uuid=str(scene.encounter.uuid),
        terminal_source_event_cursor=capture.terminal_event_cursor,
        terminal_combat_log_cursor=capture.terminal_combat_log_cursor,
        opened_partition_count=0,
        membership_replays=(),
    )
    runtime_root = tmp_path / "runtime"
    manager = HostedWorkerManager(runtime_root)
    WorkerTerminalSpool(manager.runtime_directory(game_id)).publish(
        game_id=game_id,
        worker_instance_id=worker.worker_id,
        worker_generation=worker.worker_generation,
        summary=summary,
        objective_replay=objective,
        subjective_replay=subjective,
    )

    service = GameGatewayService(
        repository,
        manager,
        RuntimeAuthorityCache(),
        GameArtifactStore(tmp_path / "artifacts"),
        capability_pepper=b"restart-test-pepper",
    )

    adopted = repository.get_game(game.game_id)
    assert adopted.lifecycle_state is GameLifecycleState.ENDED
    assert adopted.terminal_reason == "restart adoption"
    manifest = repository.get_worker_terminal_ready_manifest(game.game_id)
    assert manifest.adopted_at is not None
    assert len(repository.list_artifacts(game.game_id)) == 2
    assert repository.get_current_summary(game.game_id).summary == summary.summary

    asyncio.run(service.close())
    repository.close()
