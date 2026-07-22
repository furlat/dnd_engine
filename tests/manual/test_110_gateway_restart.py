"""Focused restart reconciliation for the multi-game gateway."""

from __future__ import annotations

import asyncio
from pathlib import Path

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
from server.game_gateway import GameGatewayService
from server.hosted_worker import HostedWorkerManager
from server.runtime_authority import RuntimeAuthorityCache


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
