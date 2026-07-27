"""Focused migration and canonical-contract tests for the game directory."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

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
    assert version_row[1] == MIGRATIONS[-1].name
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
        "character_definitions",
        "character_holdings_revisions",
        "character_loadout_revisions",
        "character_deployment_leases",
        "character_advancement_awards",
        "character_settlements",
        "profile_settings",
        "directory_mutation_receipts",
    }.issubset(foreign_key_tables)

    restarted = _open(database_path)
    restarted.close()

    connection = sqlite3.connect(database_path)
    migration_count = connection.execute(
        "SELECT COUNT(*) FROM schema_migrations"
    ).fetchone()[0]
    connection.close()
    assert migration_count == LATEST_SCHEMA_VERSION


def test_schema2_definition_migration_preserves_v1_and_rejects_unknown_versions(
    tmp_path: Path,
) -> None:
    """The v7 table hard cut admits exactly the discriminated 1|2 contract."""

    database_path = tmp_path / "directory-v6.sqlite3"
    connection = sqlite3.connect(database_path, isolation_level=None)
    configure_connection(connection, 5_000)
    apply_migrations(connection, NOW, migrations=MIGRATIONS[:6])
    principal_id = str(uuid4())
    character_id = str(uuid4())
    timestamp = NOW.isoformat().replace("+00:00", "Z")
    connection.execute(
        """
        INSERT INTO principals(
            principal_id, principal_kind, display_name, created_at,
            metadata_json, metadata_digest
        ) VALUES (?, 'human', 'Player', ?, '{}', ?)
        """,
        (principal_id, timestamp, canonical_digest({})),
    )
    connection.execute(
        """
        INSERT INTO characters(
            character_id, owner_principal_id, display_name,
            preset_configuration_id, status, created_at, updated_at
        ) VALUES (?, ?, 'Legacy Hero', 'premade.legacy', 'active', ?, ?)
        """,
        (character_id, principal_id, timestamp, timestamp),
    )
    connection.execute(
        """
        INSERT INTO character_definitions(
            character_id, definition_revision, schema_version,
            definition_json, definition_digest, created_at
        ) VALUES (?, 1, 1, '{}', ?, ?)
        """,
        (character_id, "a" * 64, timestamp),
    )

    assert apply_migrations(connection, NOW) == LATEST_SCHEMA_VERSION
    preserved = connection.execute(
        """
        SELECT schema_version, definition_digest
        FROM character_definitions
        WHERE character_id = ? AND definition_revision = 1
        """,
        (character_id,),
    ).fetchone()
    assert tuple(preserved) == (1, "a" * 64)
    connection.execute(
        """
        INSERT INTO character_definitions(
            character_id, definition_revision, schema_version,
            definition_json, definition_digest, created_at
        ) VALUES (?, 2, 2, '{}', ?, ?)
        """,
        (character_id, "b" * 64, timestamp),
    )
    with pytest.raises(sqlite3.IntegrityError, match="schema_version"):
        connection.execute(
            """
            INSERT INTO character_definitions(
                character_id, definition_revision, schema_version,
                definition_json, definition_digest, created_at
            ) VALUES (?, 3, 3, '{}', ?, ?)
            """,
            (character_id, "c" * 64, timestamp),
        )
    connection.close()


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


def test_local_execution_migration_rebuilds_games_without_losing_rows_or_schema(
    tmp_path: Path,
) -> None:
    """The execution-kind hard cut preserves the referenced games table exactly."""

    database_path = tmp_path / "directory-v5.sqlite3"
    connection = sqlite3.connect(database_path, isolation_level=None)
    configure_connection(connection, 5_000)
    apply_migrations(connection, NOW, migrations=MIGRATIONS[:5])
    timestamp = NOW.isoformat().replace("+00:00", "Z")
    owner_id = "00000000-0000-0000-0000-000000000011"
    game_id = "00000000-0000-0000-0000-000000000012"
    membership_id = "00000000-0000-0000-0000-000000000013"
    connection.execute(
        """
        INSERT INTO principals(
            principal_id, principal_kind, display_name, credential_hash,
            created_at, last_seen_at, disabled_at, metadata_json,
            metadata_digest
        ) VALUES (?, 'human', 'Local Migration Owner', NULL, ?, NULL, NULL,
                  '{}', ?)
        """,
        (owner_id, timestamp, canonical_digest({})),
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
        ) VALUES (?, NULL, NULL, NULL, ?, 'active', 'private', 'disabled',
                  'hosted', 'test', 'preserved', 'Preserved Game', '{}', ?,
                  41, 'test', 'test', 'content', ?, 3)
        """,
        (game_id, owner_id, canonical_digest({}), timestamp),
    )
    connection.execute(
        """
        INSERT INTO game_memberships(
            membership_id, game_id, principal_id, role, side_id,
            controller_kind, membership_state, may_connect,
            may_observe_public_state, may_observe_subjective_state,
            may_control_entities, may_view_agent_telemetry,
            may_manage_members, may_manage_game,
            may_view_objective_replay, subjective_source_membership_id,
            authority_epoch, joined_at, disconnected_at, revoked_at, left_at
        ) VALUES (?, ?, ?, 'owner', NULL, 'human', 'active', 1, 1, 1, 1,
                  0, 1, 1, 1, NULL, 1, ?, NULL, NULL, NULL)
        """,
        (membership_id, game_id, owner_id, timestamp),
    )
    old_columns = tuple(
        row["name"] for row in connection.execute("PRAGMA table_info(games)")
    )
    old_triggers = tuple(
        tuple(row)
        for row in connection.execute(
            """
            SELECT name, tbl_name, sql
            FROM sqlite_master
            WHERE type = 'trigger'
            ORDER BY name
            """
        )
    )

    apply_migrations(connection, NOW, migrations=MIGRATIONS[:6])

    new_columns = tuple(
        row["name"] for row in connection.execute("PRAGMA table_info(games)")
    )
    game_row = connection.execute(
        """
        SELECT execution_kind, display_name, seed, row_version
        FROM games WHERE game_id = ?
        """,
        (game_id,),
    ).fetchone()
    membership_row = connection.execute(
        "SELECT game_id, principal_id FROM game_memberships WHERE membership_id = ?",
        (membership_id,),
    ).fetchone()
    game_indexes = {
        row["name"] for row in connection.execute("PRAGMA index_list(games)")
    }
    new_triggers = tuple(
        tuple(row)
        for row in connection.execute(
            """
            SELECT name, tbl_name, sql
            FROM sqlite_master
            WHERE type = 'trigger'
            ORDER BY name
            """
        )
    )
    foreign_key_violations = connection.execute("PRAGMA foreign_key_check").fetchall()
    foreign_keys_enabled = connection.execute("PRAGMA foreign_keys").fetchone()[0]
    connection.execute(
        """
        INSERT INTO games(
            game_id, engine_game_id, worker_id, worker_generation,
            created_by_principal_id, lifecycle_state, visibility_policy,
            observer_policy, execution_kind, scenario_kind, scenario_id,
            display_name, creation_manifest_json, creation_manifest_digest,
            seed, ruleset_version, engine_version, content_digest, created_at,
            row_version
        ) VALUES (?, NULL, NULL, NULL, ?, 'reserved', 'private', 'disabled',
                  'local', 'test', 'local', 'Local Game', '{}', ?,
                  NULL, 'test', 'test', 'content', ?, 1)
        """,
        (
            "00000000-0000-0000-0000-000000000014",
            owner_id,
            canonical_digest({}),
            timestamp,
        ),
    )
    connection.close()

    assert new_columns == old_columns
    assert tuple(game_row) == ("hosted", "Preserved Game", 41, 3)
    assert tuple(membership_row) == (game_id, owner_id)
    assert {
        "games_lifecycle_created_idx",
        "games_worker_idx",
    }.issubset(game_indexes)
    assert new_triggers == old_triggers
    assert foreign_key_violations == []
    assert foreign_keys_enabled == 1


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
