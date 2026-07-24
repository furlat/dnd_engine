"""Focused migration and canonical-contract tests for the game directory."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from server.game_directory.canonical import canonical_digest, canonical_json
from server.game_directory.contracts import PrincipalCreate, PrincipalKind
from server.game_directory.errors import MigrationError
from server.game_directory.migrations import (
    INITIAL_SCHEMA,
    LATEST_SCHEMA_VERSION,
    MIGRATIONS,
    PLAYER_IDENTITIES_AND_CHARACTERS,
    apply_migrations,
    configure_connection,
)
from server.game_directory.repository import GameDirectoryRepository

NOW = datetime(2026, 7, 21, 18, 0, tzinfo=UTC)
PEPPER = b"test-only-directory-pepper"


def _open(path: Path) -> GameDirectoryRepository:
    """Open a deterministic repository for a focused test."""

    return GameDirectoryRepository(path, capability_pepper=PEPPER, clock=lambda: NOW)


def test_fresh_migration_configures_sqlite_and_is_restart_idempotent(tmp_path: Path) -> None:
    """A fresh file receives the exact versioned schema and WAL settings."""

    database_path = tmp_path / "directory.sqlite3"
    repository = _open(database_path)
    repository.close()

    connection = sqlite3.connect(database_path)
    version_row = connection.execute(
        "SELECT version, name, checksum FROM schema_migrations ORDER BY version DESC LIMIT 1"
    ).fetchone()
    journal_mode = connection.execute("PRAGMA journal_mode").fetchone()[0]
    foreign_key_tables = {
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
    }
    connection.close()

    assert version_row is not None
    assert version_row[0] == LATEST_SCHEMA_VERSION
    assert version_row[1] == "subjective_replay_artifact"
    assert len(version_row[2]) == 64
    assert journal_mode == "wal"
    assert {
        "principals",
        "workers",
        "games",
        "game_memberships",
        "entity_assignments",
        "access_grants",
        "attachments",
        "directory_events",
        "game_artifacts",
        "game_summaries",
        "rating_runs",
        "rating_admissions",
        "rating_estimates",
        "player_identities",
        "principal_credentials",
        "characters",
        "character_deployments",
    }.issubset(foreign_key_tables)

    restarted = _open(database_path)
    restarted.close()

    connection = sqlite3.connect(database_path)
    migration_count = connection.execute(
        "SELECT COUNT(*) FROM schema_migrations"
    ).fetchone()[0]
    connection.close()
    assert migration_count == LATEST_SCHEMA_VERSION


def test_subjective_replay_migration_preserves_v2_artifact_rows(
    tmp_path: Path,
) -> None:
    """The new artifact kind upgrades an existing v2 directory losslessly."""

    database_path = tmp_path / "directory-v2.sqlite3"
    connection = sqlite3.connect(database_path, isolation_level=None)
    configure_connection(connection, 5_000)
    apply_migrations(
        connection,
        NOW,
        migrations=(INITIAL_SCHEMA, PLAYER_IDENTITIES_AND_CHARACTERS),
    )
    timestamp = NOW.isoformat().replace("+00:00", "Z")
    connection.execute(
        """
        INSERT INTO principals(
            principal_id, principal_kind, display_name, credential_hash,
            created_at, last_seen_at, disabled_at, metadata_json,
            metadata_digest
        ) VALUES (?, 'human', 'Migration Owner', NULL, ?, NULL, NULL, '{}', ?)
        """,
        ("00000000-0000-0000-0000-000000000001", timestamp, canonical_digest({})),
    )
    connection.execute(
        """
        INSERT INTO games(
            game_id, engine_game_id, worker_id, worker_generation,
            created_by_principal_id, lifecycle_state, visibility_policy,
            observer_policy, execution_kind, scenario_kind, scenario_id,
            display_name, creation_manifest_json, creation_manifest_digest,
            seed, ruleset_version, engine_version, content_digest, created_at,
            row_version
        ) VALUES (?, NULL, NULL, NULL, ?, 'ended', 'private', 'members',
                  'hosted', 'test', 'migration', 'Migration Game', '{}', ?,
                  NULL, 'test', 'test', 'content', ?, 1)
        """,
        (
            "00000000-0000-0000-0000-000000000002",
            "00000000-0000-0000-0000-000000000001",
            canonical_digest({}),
            timestamp,
        ),
    )
    connection.execute(
        """
        INSERT INTO game_artifacts(
            artifact_id, game_id, artifact_kind, schema_version, media_type,
            uri, byte_size, content_digest, created_at, producer_kind,
            producer_version
        ) VALUES (?, ?, 'replay_bundle', 'objective.v1', 'application/json',
                  'file:///objective.json', 7, ?, ?, 'worker', 'test')
        """,
        (
            "00000000-0000-0000-0000-000000000003",
            "00000000-0000-0000-0000-000000000002",
            "a" * 64,
            timestamp,
        ),
    )

    apply_migrations(connection, NOW, migrations=MIGRATIONS)
    row = connection.execute(
        "SELECT artifact_kind, content_digest FROM game_artifacts"
    ).fetchone()
    connection.close()

    assert tuple(row) == ("replay_bundle", "a" * 64)
    restarted = _open(database_path)
    restarted.close()


def test_migration_checksum_drift_stops_repository_startup(tmp_path: Path) -> None:
    """A changed historical migration is never silently accepted."""

    database_path = tmp_path / "directory.sqlite3"
    repository = _open(database_path)
    repository.close()

    connection = sqlite3.connect(database_path)
    connection.execute(
        "UPDATE schema_migrations SET checksum = ? WHERE version = ?",
        ("0" * 64, LATEST_SCHEMA_VERSION),
    )
    connection.commit()
    connection.close()

    with pytest.raises(MigrationError, match="checksum drift"):
        _open(database_path)


def test_canonical_json_and_principal_round_trip_are_exact(tmp_path: Path) -> None:
    """Canonical object ordering and the seven-column principal insert remain stable."""

    left = {"z": [3, 2, 1], "a": {"two": 2, "one": 1}}
    right = {"a": {"one": 1, "two": 2}, "z": [3, 2, 1]}
    assert canonical_json(left) == canonical_json(right)
    assert canonical_digest(left) == canonical_digest(right)

    repository = _open(tmp_path / "directory.sqlite3")
    request = PrincipalCreate(
        principal_kind=PrincipalKind.HUMAN,
        display_name="Tommaso",
        credential_hash="external-auth-digest",
        metadata=left,
    )
    created = repository.create_principal(request)
    loaded = repository.get_principal(request.principal_id)
    repository.close()

    assert created == loaded
    assert loaded.display_name == "Tommaso"
    assert loaded.credential_hash == "external-auth-digest"
    assert loaded.metadata == left
    assert loaded.metadata_digest == canonical_digest(left)


def test_directory_contracts_reject_unknown_fields() -> None:
    """Control-plane contracts fail closed on unrecognized wire data."""

    with pytest.raises(ValidationError, match="extra_forbidden"):
        PrincipalCreate.model_validate(
            {
                "principal_kind": "human",
                "display_name": "Player",
                "metadata": {},
                "surprise": "not part of the contract",
            }
        )
