"""Focused proofs for directory exclusion from gameplay hot paths."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from server.game_directory.contracts import PrincipalCreate, PrincipalKind
from server.game_directory.errors import (
    HotPathDatabaseAccessError,
    InjectedRepositoryFailure,
)
from server.game_directory.repository import GameDirectoryRepository

NOW = datetime(2026, 7, 21, 20, 0, tzinfo=UTC)


def _open(path: Path) -> GameDirectoryRepository:
    """Open a deterministic repository for exclusion instrumentation tests."""

    return GameDirectoryRepository(
        path,
        capability_pepper=b"hot-path-test-pepper",
        clock=lambda: NOW,
    )


def test_hot_path_guard_blocks_database_access_before_sqlite(tmp_path: Path) -> None:
    """An annotated runtime path cannot accidentally touch the directory."""

    repository = _open(tmp_path / "directory.sqlite3")
    principal = repository.create_principal(
        PrincipalCreate(principal_kind=PrincipalKind.SYSTEM_AI, display_name="Runtime")
    )
    repository.reset_metrics()

    hot_state = {"event_cursor": 10, "commands": 0}
    with repository.forbid_hot_path_access():
        hot_state["event_cursor"] += 1
        hot_state["commands"] += 1

    clean_metrics = repository.metrics()
    assert hot_state == {"event_cursor": 11, "commands": 1}
    assert clean_metrics.total_operations == 0

    with pytest.raises(HotPathDatabaseAccessError, match="get_principal"):
        with repository.forbid_hot_path_access():
            repository.get_principal(principal.principal_id)

    blocked_metrics = repository.metrics()
    assert blocked_metrics.total_operations == 1
    assert blocked_metrics.successful_operations == 0
    assert blocked_metrics.failed_operations == 1
    assert blocked_metrics.blocked_hot_path_operations == 1
    assert blocked_metrics.by_operation == {"get_principal": 1}
    assert repository.get_principal(principal.principal_id) == principal
    repository.close()


def test_repository_fail_injection_leaves_hot_state_independent(tmp_path: Path) -> None:
    """Armed repository failure cannot affect local runtime work that has no dependency."""

    repository = _open(tmp_path / "directory.sqlite3")
    principal = repository.create_principal(
        PrincipalCreate(principal_kind=PrincipalKind.CODEX, display_name="Codex")
    )
    repository.reset_metrics()

    local_runtime_events: list[dict[str, int | str]] = []
    with repository.inject_failures():
        local_runtime_events.append({"cursor": 1, "type": "turn_started"})
        local_runtime_events.append({"cursor": 2, "type": "action_completed"})
        with pytest.raises(InjectedRepositoryFailure, match="get_principal"):
            repository.get_principal(principal.principal_id)

    assert local_runtime_events == [
        {"cursor": 1, "type": "turn_started"},
        {"cursor": 2, "type": "action_completed"},
    ]
    metrics = repository.metrics()
    assert metrics.total_operations == 1
    assert metrics.injected_failures == 1
    assert metrics.failed_operations == 1
    assert repository.get_principal(principal.principal_id) == principal
    repository.close()
