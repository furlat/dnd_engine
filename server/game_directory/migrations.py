"""Numbered checksum-verified SQLite migrations for the game directory."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime

from server.game_directory.canonical import canonical_digest, datetime_to_text
from server.game_directory.errors import MigrationError


@dataclass(frozen=True, slots=True)
class Migration:
    """One immutable ordered schema migration."""

    version: int
    name: str
    statements: tuple[str, ...]

    @property
    def checksum(self) -> str:
        """Return the deterministic checksum of migration identity and SQL."""

        return canonical_digest(
            {
                "version": self.version,
                "name": self.name,
                "statements": self.statements,
            }
        )


INITIAL_SCHEMA = Migration(
    version=1,
    name="initial_game_directory",
    statements=(
        """
        CREATE TABLE principals (
            principal_id TEXT PRIMARY KEY,
            principal_kind TEXT NOT NULL CHECK (principal_kind IN ('human', 'codex', 'service', 'system_ai')),
            display_name TEXT NOT NULL CHECK (length(display_name) > 0),
            credential_hash TEXT,
            created_at TEXT NOT NULL,
            last_seen_at TEXT,
            disabled_at TEXT,
            metadata_json TEXT NOT NULL,
            metadata_digest TEXT NOT NULL
        )
        """,
        """
        CREATE TABLE workers (
            worker_id TEXT PRIMARY KEY,
            worker_generation INTEGER NOT NULL CHECK (worker_generation >= 1),
            state TEXT NOT NULL CHECK (state IN ('starting', 'ready', 'active', 'ended', 'stopping', 'stopped', 'failed', 'lost')),
            pid INTEGER CHECK (pid IS NULL OR pid >= 1),
            process_group_id INTEGER CHECK (process_group_id IS NULL OR process_group_id >= 1),
            host_id TEXT NOT NULL,
            transport_kind TEXT NOT NULL CHECK (transport_kind IN ('unix_socket', 'loopback_tcp')),
            private_locator TEXT NOT NULL,
            started_at TEXT NOT NULL,
            last_heartbeat_at TEXT,
            lease_expires_at TEXT,
            stopped_at TEXT,
            protocol_hash TEXT NOT NULL,
            engine_version TEXT NOT NULL,
            failure_code TEXT,
            failure_detail_json TEXT NOT NULL,
            UNIQUE (worker_id, worker_generation)
        )
        """,
        """
        CREATE TABLE games (
            game_id TEXT PRIMARY KEY,
            engine_game_id TEXT,
            worker_id TEXT REFERENCES workers(worker_id),
            worker_generation INTEGER CHECK (worker_generation IS NULL OR worker_generation >= 1),
            created_by_principal_id TEXT NOT NULL REFERENCES principals(principal_id),
            lifecycle_state TEXT NOT NULL CHECK (lifecycle_state IN ('reserved', 'starting', 'active', 'ended', 'failed', 'interrupted', 'archived')),
            visibility_policy TEXT NOT NULL CHECK (visibility_policy IN ('public', 'unlisted', 'private')),
            observer_policy TEXT NOT NULL CHECK (observer_policy IN ('public', 'members', 'disabled')),
            execution_kind TEXT NOT NULL CHECK (execution_kind IN ('hosted', 'evaluation', 'imported')),
            scenario_kind TEXT NOT NULL,
            scenario_id TEXT NOT NULL,
            display_name TEXT NOT NULL,
            creation_manifest_json TEXT NOT NULL,
            creation_manifest_digest TEXT NOT NULL,
            seed INTEGER,
            ruleset_version TEXT NOT NULL,
            engine_version TEXT NOT NULL,
            content_digest TEXT NOT NULL,
            created_at TEXT NOT NULL,
            started_at TEXT,
            ended_at TEXT,
            archived_at TEXT,
            terminal_reason TEXT,
            winner_side_id TEXT,
            final_event_cursor INTEGER CHECK (final_event_cursor IS NULL OR final_event_cursor >= 0),
            final_combat_log_cursor INTEGER CHECK (final_combat_log_cursor IS NULL OR final_combat_log_cursor >= 0),
            current_summary_digest TEXT,
            row_version INTEGER NOT NULL DEFAULT 1 CHECK (row_version >= 1),
            CHECK ((worker_id IS NULL) = (worker_generation IS NULL))
        )
        """,
        "CREATE INDEX games_lifecycle_created_idx ON games(lifecycle_state, created_at)",
        "CREATE INDEX games_worker_idx ON games(worker_id, worker_generation)",
        """
        CREATE TABLE game_memberships (
            membership_id TEXT PRIMARY KEY,
            game_id TEXT NOT NULL REFERENCES games(game_id) ON DELETE CASCADE,
            principal_id TEXT NOT NULL REFERENCES principals(principal_id),
            role TEXT NOT NULL CHECK (role IN ('owner', 'player', 'observer', 'agent', 'referee', 'administrator')),
            side_id TEXT,
            controller_kind TEXT,
            membership_state TEXT NOT NULL CHECK (membership_state IN ('invited', 'active', 'disconnected', 'revoked', 'left')),
            may_connect INTEGER NOT NULL CHECK (may_connect IN (0, 1)),
            may_observe_public_state INTEGER NOT NULL CHECK (may_observe_public_state IN (0, 1)),
            may_observe_subjective_state INTEGER NOT NULL CHECK (may_observe_subjective_state IN (0, 1)),
            may_control_entities INTEGER NOT NULL CHECK (may_control_entities IN (0, 1)),
            may_view_agent_telemetry INTEGER NOT NULL CHECK (may_view_agent_telemetry IN (0, 1)),
            may_manage_members INTEGER NOT NULL CHECK (may_manage_members IN (0, 1)),
            may_manage_game INTEGER NOT NULL CHECK (may_manage_game IN (0, 1)),
            may_view_objective_replay INTEGER NOT NULL CHECK (may_view_objective_replay IN (0, 1)),
            subjective_source_membership_id TEXT REFERENCES game_memberships(membership_id),
            authority_epoch INTEGER NOT NULL CHECK (authority_epoch >= 1),
            joined_at TEXT NOT NULL,
            disconnected_at TEXT,
            revoked_at TEXT,
            left_at TEXT
        )
        """,
        """
        CREATE UNIQUE INDEX active_membership_identity_idx
        ON game_memberships(game_id, principal_id, role, COALESCE(side_id, ''))
        WHERE membership_state IN ('invited', 'active', 'disconnected')
        """,
        "CREATE INDEX memberships_game_idx ON game_memberships(game_id, membership_state)",
        """
        CREATE TABLE entity_assignments (
            assignment_id TEXT PRIMARY KEY,
            game_id TEXT NOT NULL REFERENCES games(game_id) ON DELETE CASCADE,
            membership_id TEXT NOT NULL REFERENCES game_memberships(membership_id) ON DELETE CASCADE,
            entity_uuid TEXT NOT NULL,
            entity_name TEXT NOT NULL,
            faction TEXT,
            side_id TEXT,
            controller_kind TEXT NOT NULL,
            assigned_at TEXT NOT NULL,
            released_at TEXT,
            authority_epoch INTEGER NOT NULL CHECK (authority_epoch >= 1)
        )
        """,
        """
        CREATE UNIQUE INDEX active_entity_assignment_idx
        ON entity_assignments(game_id, entity_uuid)
        WHERE released_at IS NULL
        """,
        "CREATE INDEX assignments_membership_idx ON entity_assignments(membership_id, released_at)",
        """
        CREATE TABLE access_grants (
            grant_id TEXT PRIMARY KEY,
            game_id TEXT NOT NULL REFERENCES games(game_id) ON DELETE CASCADE,
            membership_id TEXT REFERENCES game_memberships(membership_id) ON DELETE CASCADE,
            issued_to_principal_id TEXT REFERENCES principals(principal_id),
            grant_kind TEXT NOT NULL CHECK (grant_kind IN ('invite', 'reconnect', 'observe', 'agent_attach', 'admin')),
            secret_hash TEXT NOT NULL,
            scope_json TEXT NOT NULL,
            scope_digest TEXT NOT NULL,
            issued_at TEXT NOT NULL,
            expires_at TEXT,
            revoked_at TEXT,
            max_uses INTEGER CHECK (max_uses IS NULL OR max_uses >= 1),
            uses INTEGER NOT NULL DEFAULT 0 CHECK (uses >= 0),
            issued_by_principal_id TEXT NOT NULL REFERENCES principals(principal_id)
        )
        """,
        "CREATE INDEX grants_game_kind_idx ON access_grants(game_id, grant_kind, revoked_at)",
        """
        CREATE TABLE attachments (
            attachment_id TEXT PRIMARY KEY,
            runtime_session_id TEXT NOT NULL,
            game_id TEXT NOT NULL REFERENCES games(game_id) ON DELETE CASCADE,
            membership_id TEXT NOT NULL REFERENCES game_memberships(membership_id) ON DELETE CASCADE,
            worker_id TEXT NOT NULL REFERENCES workers(worker_id),
            worker_generation INTEGER NOT NULL CHECK (worker_generation >= 1),
            client_kind TEXT NOT NULL CHECK (client_kind IN ('neuroclient', 'codex_cli', 'external_ai', 'observer_tool')),
            client_instance_id TEXT NOT NULL,
            state TEXT NOT NULL CHECK (state IN ('connected', 'disconnected', 'expired', 'revoked')),
            runtime_token_hash TEXT NOT NULL,
            connected_at TEXT NOT NULL,
            last_seen_at TEXT,
            disconnected_at TEXT,
            disconnect_reason TEXT,
            expires_at TEXT,
            last_event_cursor INTEGER CHECK (last_event_cursor IS NULL OR last_event_cursor >= 0),
            last_combat_log_cursor INTEGER CHECK (last_combat_log_cursor IS NULL OR last_combat_log_cursor >= 0),
            authority_epoch INTEGER NOT NULL CHECK (authority_epoch >= 1),
            UNIQUE (attachment_id, game_id)
        )
        """,
        "CREATE INDEX attachments_membership_idx ON attachments(membership_id, state)",
        "CREATE INDEX attachments_reconnect_idx ON attachments(membership_id, connected_at DESC)",
        """
        CREATE TABLE directory_events (
            cursor INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id TEXT NOT NULL UNIQUE,
            game_id TEXT REFERENCES games(game_id) ON DELETE CASCADE,
            event_type TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            payload_digest TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """,
        "CREATE INDEX directory_events_game_cursor_idx ON directory_events(game_id, cursor)",
        """
        CREATE TABLE game_artifacts (
            artifact_id TEXT PRIMARY KEY,
            game_id TEXT REFERENCES games(game_id) ON DELETE CASCADE,
            artifact_kind TEXT NOT NULL CHECK (artifact_kind IN ('creation_manifest', 'objective_event_history', 'combat_log', 'subjective_transcript', 'agent_telemetry', 'terminal_summary', 'replay_bundle', 'rating_output')),
            schema_version TEXT NOT NULL,
            media_type TEXT NOT NULL,
            uri TEXT NOT NULL,
            byte_size INTEGER NOT NULL CHECK (byte_size >= 0),
            content_digest TEXT NOT NULL,
            created_at TEXT NOT NULL,
            producer_kind TEXT NOT NULL CHECK (producer_kind IN ('directory', 'worker', 'evaluator', 'importer')),
            producer_version TEXT NOT NULL
        )
        """,
        """
        CREATE UNIQUE INDEX artifact_content_identity_idx
        ON game_artifacts(COALESCE(game_id, ''), artifact_kind, content_digest)
        """,
        """
        CREATE TABLE game_summaries (
            summary_id TEXT PRIMARY KEY,
            game_id TEXT NOT NULL REFERENCES games(game_id) ON DELETE CASCADE,
            schema_version TEXT NOT NULL,
            summary_revision INTEGER NOT NULL CHECK (summary_revision >= 1),
            summary_json TEXT NOT NULL,
            summary_digest TEXT NOT NULL,
            winner_side_id TEXT,
            terminal_reason TEXT NOT NULL,
            round_count INTEGER NOT NULL CHECK (round_count >= 0),
            turn_count INTEGER NOT NULL CHECK (turn_count >= 0),
            duration_ms INTEGER NOT NULL CHECK (duration_ms >= 0),
            source_event_digest TEXT NOT NULL,
            source_combat_log_digest TEXT NOT NULL,
            created_at TEXT NOT NULL,
            supersedes_summary_id TEXT REFERENCES game_summaries(summary_id),
            is_current INTEGER NOT NULL CHECK (is_current IN (0, 1)),
            UNIQUE (game_id, summary_revision),
            UNIQUE (game_id, summary_digest)
        )
        """,
        """
        CREATE UNIQUE INDEX current_game_summary_idx
        ON game_summaries(game_id)
        WHERE is_current = 1
        """,
        """
        CREATE TABLE rating_runs (
            rating_run_id TEXT PRIMARY KEY,
            algorithm_id TEXT NOT NULL,
            algorithm_version TEXT NOT NULL,
            parameters_json TEXT NOT NULL,
            parameters_digest TEXT NOT NULL,
            selection_query_json TEXT NOT NULL,
            selection_query_digest TEXT NOT NULL,
            compatibility_constraints_json TEXT NOT NULL,
            compatibility_digest TEXT NOT NULL,
            status TEXT NOT NULL CHECK (status IN ('reserved', 'running', 'completed', 'failed')),
            created_at TEXT NOT NULL,
            completed_at TEXT,
            output_artifact_digest TEXT
        )
        """,
        """
        CREATE TABLE rating_admissions (
            admission_id TEXT PRIMARY KEY,
            rating_run_id TEXT NOT NULL REFERENCES rating_runs(rating_run_id) ON DELETE CASCADE,
            game_id TEXT NOT NULL,
            summary_digest TEXT NOT NULL,
            admitted INTEGER NOT NULL CHECK (admitted IN (0, 1)),
            exclusion_reason_code TEXT,
            exclusion_detail_json TEXT NOT NULL,
            treatment_id TEXT NOT NULL,
            configuration_id TEXT NOT NULL,
            weight REAL NOT NULL CHECK (weight > 0),
            created_at TEXT NOT NULL,
            FOREIGN KEY (game_id, summary_digest) REFERENCES game_summaries(game_id, summary_digest),
            UNIQUE (rating_run_id, game_id, summary_digest, treatment_id, configuration_id)
        )
        """,
        """
        CREATE TABLE rating_estimates (
            estimate_id TEXT PRIMARY KEY,
            rating_run_id TEXT NOT NULL REFERENCES rating_runs(rating_run_id) ON DELETE CASCADE,
            subject_id TEXT NOT NULL,
            estimate REAL NOT NULL,
            uncertainty REAL NOT NULL CHECK (uncertainty >= 0),
            games INTEGER NOT NULL CHECK (games >= 0),
            wins INTEGER NOT NULL CHECK (wins >= 0),
            losses INTEGER NOT NULL CHECK (losses >= 0),
            draws INTEGER NOT NULL CHECK (draws >= 0),
            rank INTEGER CHECK (rank IS NULL OR rank >= 1),
            diagnostics_json TEXT NOT NULL,
            diagnostics_digest TEXT NOT NULL,
            created_at TEXT NOT NULL,
            UNIQUE (rating_run_id, subject_id)
        )
        """,
    ),
)

PLAYER_IDENTITIES_AND_CHARACTERS = Migration(
    version=2,
    name="player_identities_and_characters",
    statements=(
        """
        CREATE TABLE player_identities (
            identity_key TEXT PRIMARY KEY,
            principal_id TEXT NOT NULL UNIQUE REFERENCES principals(principal_id),
            display_name TEXT NOT NULL CHECK (length(display_name) > 0),
            created_at TEXT NOT NULL
        )
        """,
        """
        CREATE TABLE principal_credentials (
            credential_id TEXT PRIMARY KEY,
            principal_id TEXT NOT NULL REFERENCES principals(principal_id) ON DELETE CASCADE,
            client_instance_id TEXT NOT NULL,
            secret_hash TEXT NOT NULL,
            issued_at TEXT NOT NULL,
            last_seen_at TEXT,
            revoked_at TEXT,
            UNIQUE (principal_id, secret_hash)
        )
        """,
        "CREATE INDEX principal_credentials_lookup_idx ON principal_credentials(principal_id, secret_hash, revoked_at)",
        """
        CREATE TABLE characters (
            character_id TEXT PRIMARY KEY,
            owner_principal_id TEXT NOT NULL REFERENCES principals(principal_id),
            display_name TEXT NOT NULL CHECK (length(display_name) > 0),
            preset_configuration_id TEXT NOT NULL,
            status TEXT NOT NULL CHECK (status IN ('active', 'retired')),
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            row_version INTEGER NOT NULL DEFAULT 1 CHECK (row_version >= 1)
        )
        """,
        "CREATE INDEX characters_owner_status_idx ON characters(owner_principal_id, status, created_at)",
        """
        CREATE TABLE character_deployments (
            deployment_id TEXT PRIMARY KEY,
            game_id TEXT NOT NULL REFERENCES games(game_id) ON DELETE CASCADE,
            membership_id TEXT NOT NULL REFERENCES game_memberships(membership_id) ON DELETE CASCADE,
            character_id TEXT NOT NULL REFERENCES characters(character_id),
            entity_uuid TEXT NOT NULL,
            deployed_at TEXT NOT NULL,
            UNIQUE (game_id, character_id),
            UNIQUE (game_id, entity_uuid)
        )
        """,
        "CREATE INDEX character_deployments_character_idx ON character_deployments(character_id, deployed_at)",
    ),
)

MIGRATIONS: tuple[Migration, ...] = (INITIAL_SCHEMA, PLAYER_IDENTITIES_AND_CHARACTERS)
LATEST_SCHEMA_VERSION = MIGRATIONS[-1].version


def configure_connection(connection: sqlite3.Connection, busy_timeout_ms: int) -> None:
    """Configure required SQLite safety and concurrency settings.

    Args:
        connection: Open SQLite connection owned by the gateway.
        busy_timeout_ms: Bounded lock wait in milliseconds.
    """

    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    connection.execute("PRAGMA synchronous = NORMAL")
    connection.execute(f"PRAGMA busy_timeout = {int(busy_timeout_ms)}")
    connection.row_factory = sqlite3.Row


def apply_migrations(
    connection: sqlite3.Connection,
    applied_at: datetime,
    migrations: tuple[Migration, ...] = MIGRATIONS,
) -> int:
    """Apply pending migrations and verify every stored checksum.

    Args:
        connection: Configured SQLite connection in autocommit mode.
        applied_at: UTC timestamp recorded for newly applied migrations.
        migrations: Ordered migration definitions, injectable for drift tests.

    Returns:
        Latest applied schema version.

    Raises:
        MigrationError: If history is newer, missing, reordered, or changed.
    """

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            checksum TEXT NOT NULL,
            applied_at TEXT NOT NULL
        )
        """
    )
    stored_rows = connection.execute(
        "SELECT version, name, checksum FROM schema_migrations ORDER BY version"
    ).fetchall()
    by_version = {migration.version: migration for migration in migrations}
    expected_versions = [migration.version for migration in migrations]
    if expected_versions != sorted(expected_versions) or len(expected_versions) != len(set(expected_versions)):
        raise MigrationError("Migration definitions must have unique ascending versions")

    for row in stored_rows:
        version = int(row["version"])
        migration = by_version.get(version)
        if migration is None:
            raise MigrationError(f"Database contains unknown migration version {version}")
        if row["name"] != migration.name or row["checksum"] != migration.checksum:
            raise MigrationError(f"Migration checksum drift detected at version {version}")

    applied_versions = {int(row["version"]) for row in stored_rows}
    timestamp = datetime_to_text(applied_at)
    for migration in migrations:
        if migration.version in applied_versions:
            continue
        connection.execute("BEGIN IMMEDIATE")
        try:
            for statement in migration.statements:
                connection.execute(statement)
            connection.execute(
                "INSERT INTO schema_migrations(version, name, checksum, applied_at) VALUES (?, ?, ?, ?)",
                (migration.version, migration.name, migration.checksum, timestamp),
            )
            connection.execute("COMMIT")
        except sqlite3.Error as exc:
            connection.execute("ROLLBACK")
            raise MigrationError(
                f"Failed to apply migration {migration.version} ({migration.name}): {exc}"
            ) from exc

    return migrations[-1].version if migrations else 0
