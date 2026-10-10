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
    requires_foreign_keys_disabled: bool = False
    requires_legacy_alter_table: bool = False

    @property
    def checksum(self) -> str:
        """Return the deterministic checksum of migration identity and SQL."""

        identity: dict[str, object] = {
            "version": self.version,
            "name": self.name,
            "statements": self.statements,
        }
        if self.requires_foreign_keys_disabled:
            identity["requires_foreign_keys_disabled"] = True
        if self.requires_legacy_alter_table:
            identity["requires_legacy_alter_table"] = True
        return canonical_digest(identity)


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

SUBJECTIVE_REPLAY_ARTIFACT = Migration(
    version=3,
    name="subjective_replay_artifact",
    statements=(
        """
        CREATE TABLE game_artifacts_with_subjective_replay (
            artifact_id TEXT PRIMARY KEY,
            game_id TEXT REFERENCES games(game_id) ON DELETE CASCADE,
            artifact_kind TEXT NOT NULL CHECK (artifact_kind IN ('creation_manifest', 'objective_event_history', 'combat_log', 'subjective_transcript', 'agent_telemetry', 'terminal_summary', 'replay_bundle', 'subjective_replay_bundle', 'rating_output')),
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
        INSERT INTO game_artifacts_with_subjective_replay(
            artifact_id, game_id, artifact_kind, schema_version,
            media_type, uri, byte_size, content_digest, created_at,
            producer_kind, producer_version
        )
        SELECT
            artifact_id, game_id, artifact_kind, schema_version,
            media_type, uri, byte_size, content_digest, created_at,
            producer_kind, producer_version
        FROM game_artifacts
        """,
        "DROP TABLE game_artifacts",
        "ALTER TABLE game_artifacts_with_subjective_replay RENAME TO game_artifacts",
        """
        CREATE UNIQUE INDEX artifact_content_identity_idx
        ON game_artifacts(COALESCE(game_id, ''), artifact_kind, content_digest)
        """,
        """
        CREATE UNIQUE INDEX terminal_replay_artifact_kind_idx
        ON game_artifacts(game_id, artifact_kind)
        WHERE artifact_kind IN ('replay_bundle', 'subjective_replay_bundle')
        """,
    ),
)

CHARACTER_REVISIONS_AND_DEPLOYMENT_LEASES = Migration(
    version=4,
    name="character_revisions_and_deployment_leases",
    statements=(
        """
        ALTER TABLE characters
        ADD COLUMN revision_state TEXT NOT NULL DEFAULT 'legacy_pending'
        CHECK (revision_state IN ('legacy_pending', 'canonical'))
        """,
        """
        ALTER TABLE characters
        ADD COLUMN current_definition_revision INTEGER
        CHECK (
            current_definition_revision IS NULL
            OR current_definition_revision >= 1
        )
        """,
        "ALTER TABLE characters ADD COLUMN current_definition_digest TEXT",
        """
        ALTER TABLE characters
        ADD COLUMN current_holdings_revision INTEGER
        CHECK (
            current_holdings_revision IS NULL
            OR current_holdings_revision >= 1
        )
        """,
        "ALTER TABLE characters ADD COLUMN current_holdings_digest TEXT",
        """
        CREATE TABLE character_definitions (
            character_id TEXT NOT NULL
                REFERENCES characters(character_id),
            definition_revision INTEGER NOT NULL
                CHECK (definition_revision >= 1),
            schema_version INTEGER NOT NULL CHECK (schema_version = 1),
            definition_json TEXT NOT NULL,
            definition_digest TEXT NOT NULL
                CHECK (length(definition_digest) = 64),
            created_at TEXT NOT NULL,
            PRIMARY KEY (character_id, definition_revision),
            UNIQUE (character_id, definition_digest)
        )
        """,
        """
        CREATE TABLE character_holdings_revisions (
            character_id TEXT NOT NULL
                REFERENCES characters(character_id),
            holdings_revision INTEGER NOT NULL
                CHECK (holdings_revision >= 1),
            schema_version INTEGER NOT NULL CHECK (schema_version = 1),
            holdings_json TEXT NOT NULL,
            holdings_digest TEXT NOT NULL
                CHECK (length(holdings_digest) = 64),
            created_at TEXT NOT NULL,
            PRIMARY KEY (character_id, holdings_revision),
            UNIQUE (character_id, holdings_digest)
        )
        """,
        """
        CREATE TRIGGER character_definitions_immutable_update
        BEFORE UPDATE ON character_definitions
        BEGIN
            SELECT RAISE(
                ABORT,
                'character definition revisions are immutable'
            );
        END
        """,
        """
        CREATE TRIGGER character_definitions_immutable_delete
        BEFORE DELETE ON character_definitions
        BEGIN
            SELECT RAISE(
                ABORT,
                'character definition revisions are immutable'
            );
        END
        """,
        """
        CREATE TRIGGER character_holdings_revisions_immutable_update
        BEFORE UPDATE ON character_holdings_revisions
        BEGIN
            SELECT RAISE(
                ABORT,
                'character holdings revisions are immutable'
            );
        END
        """,
        """
        CREATE TRIGGER character_holdings_revisions_immutable_delete
        BEFORE DELETE ON character_holdings_revisions
        BEGIN
            SELECT RAISE(
                ABORT,
                'character holdings revisions are immutable'
            );
        END
        """,
        """
        CREATE TRIGGER characters_revision_heads_insert_guard
        BEFORE INSERT ON characters
        BEGIN
            SELECT CASE
                WHEN NEW.revision_state = 'legacy_pending'
                     AND (
                         NEW.current_definition_revision IS NOT NULL
                         OR NEW.current_definition_digest IS NOT NULL
                         OR NEW.current_holdings_revision IS NOT NULL
                         OR NEW.current_holdings_digest IS NOT NULL
                     )
                THEN RAISE(
                    ABORT,
                    'legacy-pending characters cannot have revision heads'
                )
                WHEN NEW.revision_state = 'canonical'
                     AND (
                         NEW.current_definition_revision IS NULL
                         OR NEW.current_definition_digest IS NULL
                         OR NEW.current_holdings_revision IS NULL
                         OR NEW.current_holdings_digest IS NULL
                     )
                THEN RAISE(
                    ABORT,
                    'canonical characters require complete revision heads'
                )
            END;
            SELECT CASE
                WHEN NEW.revision_state = 'canonical'
                     AND NOT EXISTS (
                         SELECT 1
                         FROM character_definitions AS definition
                         WHERE definition.character_id = NEW.character_id
                           AND definition.definition_revision =
                               NEW.current_definition_revision
                           AND definition.definition_digest =
                               NEW.current_definition_digest
                     )
                THEN RAISE(
                    ABORT,
                    'canonical character definition head does not exist'
                )
            END;
            SELECT CASE
                WHEN NEW.revision_state = 'canonical'
                     AND NOT EXISTS (
                         SELECT 1
                         FROM character_holdings_revisions AS holdings
                         WHERE holdings.character_id = NEW.character_id
                           AND holdings.holdings_revision =
                               NEW.current_holdings_revision
                           AND holdings.holdings_digest =
                               NEW.current_holdings_digest
                     )
                THEN RAISE(
                    ABORT,
                    'canonical character holdings head does not exist'
                )
            END;
        END
        """,
        """
        CREATE TRIGGER characters_revision_heads_update_guard
        BEFORE UPDATE OF
            revision_state,
            current_definition_revision,
            current_definition_digest,
            current_holdings_revision,
            current_holdings_digest
        ON characters
        BEGIN
            SELECT CASE
                WHEN NEW.revision_state = 'legacy_pending'
                     AND (
                         NEW.current_definition_revision IS NOT NULL
                         OR NEW.current_definition_digest IS NOT NULL
                         OR NEW.current_holdings_revision IS NOT NULL
                         OR NEW.current_holdings_digest IS NOT NULL
                     )
                THEN RAISE(
                    ABORT,
                    'legacy-pending characters cannot have revision heads'
                )
                WHEN NEW.revision_state = 'canonical'
                     AND (
                         NEW.current_definition_revision IS NULL
                         OR NEW.current_definition_digest IS NULL
                         OR NEW.current_holdings_revision IS NULL
                         OR NEW.current_holdings_digest IS NULL
                     )
                THEN RAISE(
                    ABORT,
                    'canonical characters require complete revision heads'
                )
            END;
            SELECT CASE
                WHEN NEW.revision_state = 'canonical'
                     AND NOT EXISTS (
                         SELECT 1
                         FROM character_definitions AS definition
                         WHERE definition.character_id = NEW.character_id
                           AND definition.definition_revision =
                               NEW.current_definition_revision
                           AND definition.definition_digest =
                               NEW.current_definition_digest
                     )
                THEN RAISE(
                    ABORT,
                    'canonical character definition head does not exist'
                )
            END;
            SELECT CASE
                WHEN NEW.revision_state = 'canonical'
                     AND NOT EXISTS (
                         SELECT 1
                         FROM character_holdings_revisions AS holdings
                         WHERE holdings.character_id = NEW.character_id
                           AND holdings.holdings_revision =
                               NEW.current_holdings_revision
                           AND holdings.holdings_digest =
                               NEW.current_holdings_digest
                     )
                THEN RAISE(
                    ABORT,
                    'canonical character holdings head does not exist'
                )
            END;
            SELECT CASE
                WHEN OLD.revision_state = 'canonical'
                     AND NEW.revision_state != 'canonical'
                THEN RAISE(
                    ABORT,
                    'canonical characters cannot become legacy pending'
                )
            END;
            SELECT CASE
                WHEN OLD.revision_state = 'canonical'
                     AND (
                         NEW.current_definition_revision <
                             OLD.current_definition_revision
                         OR NEW.current_holdings_revision <
                             OLD.current_holdings_revision
                     )
                THEN RAISE(
                    ABORT,
                    'canonical character revision heads cannot move backward'
                )
            END;
        END
        """,
        """
        CREATE TABLE character_deployment_leases (
            lease_id TEXT PRIMARY KEY,
            character_id TEXT NOT NULL
                REFERENCES characters(character_id),
            game_id TEXT NOT NULL REFERENCES games(game_id) ON DELETE CASCADE,
            membership_id TEXT NOT NULL
                REFERENCES game_memberships(membership_id) ON DELETE CASCADE,
            acquired_at TEXT NOT NULL,
            released_at TEXT,
            release_reason TEXT,
            CHECK (
                (released_at IS NULL AND release_reason IS NULL)
                OR (
                    released_at IS NOT NULL
                    AND release_reason IS NOT NULL
                    AND length(release_reason) > 0
                )
            )
        )
        """,
        """
        CREATE TRIGGER character_deployment_leases_authority_guard
        BEFORE INSERT ON character_deployment_leases
        WHEN NOT EXISTS (
            SELECT 1
            FROM characters AS character
            JOIN game_memberships AS membership
              ON membership.membership_id = NEW.membership_id
            WHERE character.character_id = NEW.character_id
              AND character.owner_principal_id = membership.principal_id
              AND character.status = 'active'
              AND character.revision_state = 'canonical'
              AND membership.game_id = NEW.game_id
              AND membership.membership_state = 'active'
              AND membership.may_control_entities = 1
        )
        BEGIN
            SELECT RAISE(
                ABORT,
                'character lease requires active owner control authority'
            );
        END
        """,
        """
        CREATE UNIQUE INDEX active_character_deployment_lease_idx
        ON character_deployment_leases(character_id)
        WHERE released_at IS NULL
        """,
        """
        CREATE INDEX character_deployment_leases_game_idx
        ON character_deployment_leases(game_id, released_at)
        """,
        """
        CREATE TRIGGER character_deployment_leases_immutable_identity
        BEFORE UPDATE OF
            lease_id,
            character_id,
            game_id,
            membership_id,
            acquired_at
        ON character_deployment_leases
        BEGIN
            SELECT RAISE(
                ABORT,
                'character deployment lease identity is immutable'
            );
        END
        """,
        """
        CREATE TRIGGER character_deployment_leases_single_release
        BEFORE UPDATE OF released_at, release_reason
        ON character_deployment_leases
        WHEN OLD.released_at IS NOT NULL
        BEGIN
            SELECT RAISE(
                ABORT,
                'released character deployment leases are immutable'
            );
        END
        """,
        """
        CREATE TRIGGER character_deployment_leases_immutable_delete
        BEFORE DELETE ON character_deployment_leases
        BEGIN
            SELECT RAISE(
                ABORT,
                'character deployment lease history is immutable'
            );
        END
        """,
        "ALTER TABLE character_deployments ADD COLUMN lease_id TEXT",
        """
        ALTER TABLE character_deployments
        ADD COLUMN pin_state TEXT NOT NULL DEFAULT 'legacy_pending'
        CHECK (pin_state IN ('legacy_pending', 'pinned'))
        """,
        """
        ALTER TABLE character_deployments
        ADD COLUMN definition_revision INTEGER
        CHECK (definition_revision IS NULL OR definition_revision >= 1)
        """,
        "ALTER TABLE character_deployments ADD COLUMN definition_digest TEXT",
        """
        ALTER TABLE character_deployments
        ADD COLUMN holdings_revision INTEGER
        CHECK (holdings_revision IS NULL OR holdings_revision >= 1)
        """,
        "ALTER TABLE character_deployments ADD COLUMN holdings_digest TEXT",
        """
        CREATE TRIGGER character_deployment_pins_insert_guard
        BEFORE INSERT ON character_deployments
        BEGIN
            SELECT CASE
                WHEN NEW.pin_state = 'legacy_pending'
                     AND (
                         NEW.lease_id IS NOT NULL
                         OR NEW.definition_revision IS NOT NULL
                         OR NEW.definition_digest IS NOT NULL
                         OR NEW.holdings_revision IS NOT NULL
                         OR NEW.holdings_digest IS NOT NULL
                     )
                THEN RAISE(
                    ABORT,
                    'legacy-pending deployments cannot have revision pins'
                )
                WHEN NEW.pin_state = 'pinned'
                     AND (
                         NEW.lease_id IS NULL
                         OR NEW.definition_revision IS NULL
                         OR NEW.definition_digest IS NULL
                         OR NEW.holdings_revision IS NULL
                         OR NEW.holdings_digest IS NULL
                     )
                THEN RAISE(
                    ABORT,
                    'pinned deployments require complete revision pins'
                )
            END;
            SELECT CASE
                WHEN NEW.pin_state = 'pinned'
                     AND NOT EXISTS (
                         SELECT 1
                         FROM character_deployment_leases AS lease
                         WHERE lease.lease_id = NEW.lease_id
                           AND lease.character_id = NEW.character_id
                           AND lease.game_id = NEW.game_id
                           AND lease.membership_id = NEW.membership_id
                           AND lease.released_at IS NULL
                     )
                THEN RAISE(
                    ABORT,
                    'pinned deployment requires its active character lease'
                )
            END;
            SELECT CASE
                WHEN NEW.pin_state = 'pinned'
                     AND NOT EXISTS (
                         SELECT 1
                         FROM characters AS character
                         WHERE character.character_id = NEW.character_id
                           AND character.revision_state = 'canonical'
                           AND character.current_definition_revision =
                               NEW.definition_revision
                           AND character.current_definition_digest =
                               NEW.definition_digest
                           AND character.current_holdings_revision =
                               NEW.holdings_revision
                           AND character.current_holdings_digest =
                               NEW.holdings_digest
                     )
                THEN RAISE(
                    ABORT,
                    'deployment pins do not match current character heads'
                )
            END;
        END
        """,
        """
        CREATE TRIGGER character_deployments_immutable_update
        BEFORE UPDATE OF
            deployment_id,
            game_id,
            membership_id,
            character_id,
            entity_uuid,
            deployed_at,
            lease_id,
            pin_state,
            definition_revision,
            definition_digest,
            holdings_revision,
            holdings_digest
        ON character_deployments
        BEGIN
            SELECT RAISE(
                ABORT,
                'character deployment identity and revision lineage are immutable'
            );
        END
        """,
        """
        CREATE TRIGGER character_deployments_immutable_delete
        BEFORE DELETE ON character_deployments
        BEGIN
            SELECT RAISE(
                ABORT,
                'character deployment history is immutable'
            );
        END
        """,
    ),
)

OFFLINE_CHARACTER_LOADOUT_BACKFILL_REQUIRED = (
    "offline character loadout backfill required"
)


CHARACTER_PROFILE_PROGRESSION_FOUNDATION = Migration(
    version=5,
    name="character_profile_progression_foundation",
    statements=(
        """
        CREATE TABLE profile_settings (
            owner_principal_id TEXT PRIMARY KEY
                REFERENCES principals(principal_id) ON DELETE CASCADE,
            permissive_multiclass_prerequisites INTEGER NOT NULL DEFAULT 1
                CHECK (permissive_multiclass_prerequisites IN (0, 1)),
            multiclass_slot_rounding_policy TEXT NOT NULL
                DEFAULT 'srd_5_2_round_up'
                CHECK (
                    multiclass_slot_rounding_policy IN (
                        'srd_5_1_round_down',
                        'srd_5_2_round_up'
                    )
                ),
            allow_respec INTEGER NOT NULL DEFAULT 1
                CHECK (allow_respec IN (0, 1)),
            spell_preparation_policy TEXT NOT NULL DEFAULT 'long_rest'
                CHECK (
                    spell_preparation_policy IN (
                        'long_rest',
                        'out_of_combat'
                    )
                ),
            settings_version INTEGER NOT NULL DEFAULT 1
                CHECK (settings_version >= 1),
            ruleset_digest TEXT NOT NULL
                CHECK (
                    length(ruleset_digest) = 64
                    AND ruleset_digest NOT GLOB '*[^0-9a-f]*'
                ),
            updated_at TEXT NOT NULL
        )
        """,
        """
        CREATE TABLE character_advancement_awards (
            award_id TEXT PRIMARY KEY,
            character_id TEXT NOT NULL
                REFERENCES characters(character_id),
            level_delta INTEGER NOT NULL CHECK (level_delta > 0),
            source_kind TEXT NOT NULL
                CHECK (
                    source_kind IN (
                        'creation',
                        'game_reward',
                        'developer',
                        'migration'
                    )
                ),
            source_id TEXT NOT NULL CHECK (length(source_id) > 0),
            created_at TEXT NOT NULL,
            UNIQUE (character_id, source_kind, source_id)
        )
        """,
        """
        CREATE INDEX character_advancement_awards_character_idx
        ON character_advancement_awards(character_id, created_at, award_id)
        """,
        """
        CREATE TABLE character_loadout_revisions (
            character_id TEXT NOT NULL
                REFERENCES characters(character_id),
            loadout_revision INTEGER NOT NULL CHECK (loadout_revision >= 1),
            schema_version INTEGER NOT NULL CHECK (schema_version >= 1),
            based_on_definition_revision INTEGER NOT NULL
                CHECK (based_on_definition_revision >= 1),
            loadout_json TEXT NOT NULL,
            loadout_digest TEXT NOT NULL
                CHECK (
                    length(loadout_digest) = 64
                    AND loadout_digest NOT GLOB '*[^0-9a-f]*'
                ),
            created_at TEXT NOT NULL,
            PRIMARY KEY (character_id, loadout_revision),
            FOREIGN KEY (character_id, based_on_definition_revision)
                REFERENCES character_definitions(
                    character_id,
                    definition_revision
                )
        )
        """,
        """
        ALTER TABLE characters
        ADD COLUMN current_loadout_revision INTEGER
        CHECK (
            current_loadout_revision IS NULL
            OR current_loadout_revision >= 1
        )
        """,
        "ALTER TABLE characters ADD COLUMN current_loadout_digest TEXT",
        """
        ALTER TABLE character_deployments
        ADD COLUMN loadout_revision INTEGER
        CHECK (loadout_revision IS NULL OR loadout_revision >= 1)
        """,
        "ALTER TABLE character_deployments ADD COLUMN loadout_digest TEXT",
        """
        CREATE TABLE character_settlements (
            settlement_id TEXT PRIMARY KEY,
            deployment_id TEXT NOT NULL UNIQUE
                REFERENCES character_deployments(deployment_id),
            game_id TEXT NOT NULL REFERENCES games(game_id),
            character_id TEXT NOT NULL REFERENCES characters(character_id),
            starting_holdings_revision INTEGER NOT NULL
                CHECK (starting_holdings_revision >= 1),
            starting_holdings_digest TEXT NOT NULL
                CHECK (
                    length(starting_holdings_digest) = 64
                    AND starting_holdings_digest NOT GLOB '*[^0-9a-f]*'
                ),
            resulting_holdings_revision INTEGER NOT NULL
                CHECK (
                    resulting_holdings_revision =
                    starting_holdings_revision + 1
                ),
            resulting_holdings_digest TEXT NOT NULL
                CHECK (
                    length(resulting_holdings_digest) = 64
                    AND resulting_holdings_digest NOT GLOB '*[^0-9a-f]*'
                ),
            delta_digest TEXT NOT NULL
                CHECK (
                    length(delta_digest) = 64
                    AND delta_digest NOT GLOB '*[^0-9a-f]*'
                ),
            settled_at TEXT NOT NULL,
            FOREIGN KEY (character_id, starting_holdings_revision)
                REFERENCES character_holdings_revisions(
                    character_id,
                    holdings_revision
                ),
            FOREIGN KEY (character_id, resulting_holdings_revision)
                REFERENCES character_holdings_revisions(
                    character_id,
                    holdings_revision
                )
        )
        """,
        """
        CREATE TRIGGER profile_settings_immutable_delete
        BEFORE DELETE ON profile_settings
        BEGIN
            SELECT RAISE(ABORT, 'profile settings cannot be deleted');
        END
        """,
        """
        CREATE TRIGGER character_advancement_awards_immutable_update
        BEFORE UPDATE ON character_advancement_awards
        BEGIN
            SELECT RAISE(
                ABORT,
                'character advancement awards are immutable'
            );
        END
        """,
        """
        CREATE TRIGGER character_advancement_awards_immutable_delete
        BEFORE DELETE ON character_advancement_awards
        BEGIN
            SELECT RAISE(
                ABORT,
                'character advancement awards are immutable'
            );
        END
        """,
        """
        CREATE TRIGGER character_loadout_revisions_immutable_update
        BEFORE UPDATE ON character_loadout_revisions
        BEGIN
            SELECT RAISE(
                ABORT,
                'character loadout revisions are immutable'
            );
        END
        """,
        """
        CREATE TRIGGER character_loadout_revisions_immutable_delete
        BEFORE DELETE ON character_loadout_revisions
        BEGIN
            SELECT RAISE(
                ABORT,
                'character loadout revisions are immutable'
            );
        END
        """,
        """
        CREATE TRIGGER character_settlements_immutable_update
        BEFORE UPDATE ON character_settlements
        BEGIN
            SELECT RAISE(ABORT, 'character settlements are immutable');
        END
        """,
        """
        CREATE TRIGGER character_settlements_immutable_delete
        BEFORE DELETE ON character_settlements
        BEGIN
            SELECT RAISE(ABORT, 'character settlements are immutable');
        END
        """,
        "DROP TRIGGER characters_revision_heads_insert_guard",
        "DROP TRIGGER characters_revision_heads_update_guard",
        "DROP TRIGGER character_deployment_pins_insert_guard",
        "DROP TRIGGER character_deployments_immutable_update",
        """
        CREATE TRIGGER characters_revision_heads_insert_guard
        BEFORE INSERT ON characters
        BEGIN
            SELECT CASE
                WHEN NEW.revision_state = 'legacy_pending'
                     AND (
                         NEW.current_definition_revision IS NOT NULL
                         OR NEW.current_definition_digest IS NOT NULL
                         OR NEW.current_holdings_revision IS NOT NULL
                         OR NEW.current_holdings_digest IS NOT NULL
                         OR NEW.current_loadout_revision IS NOT NULL
                         OR NEW.current_loadout_digest IS NOT NULL
                     )
                THEN RAISE(
                    ABORT,
                    'legacy-pending characters cannot have revision heads'
                )
                WHEN NEW.revision_state = 'canonical'
                     AND (
                         NEW.current_definition_revision IS NULL
                         OR NEW.current_definition_digest IS NULL
                         OR NEW.current_holdings_revision IS NULL
                         OR NEW.current_holdings_digest IS NULL
                         OR NEW.current_loadout_revision IS NULL
                         OR NEW.current_loadout_digest IS NULL
                     )
                THEN RAISE(
                    ABORT,
                    'canonical characters require complete revision heads'
                )
            END;
            SELECT CASE
                WHEN NEW.revision_state = 'canonical'
                     AND NOT EXISTS (
                         SELECT 1
                         FROM character_definitions AS definition
                         WHERE definition.character_id = NEW.character_id
                           AND definition.definition_revision =
                               NEW.current_definition_revision
                           AND definition.definition_digest =
                               NEW.current_definition_digest
                     )
                THEN RAISE(
                    ABORT,
                    'canonical character definition head does not exist'
                )
            END;
            SELECT CASE
                WHEN NEW.revision_state = 'canonical'
                     AND NOT EXISTS (
                         SELECT 1
                         FROM character_holdings_revisions AS holdings
                         WHERE holdings.character_id = NEW.character_id
                           AND holdings.holdings_revision =
                               NEW.current_holdings_revision
                           AND holdings.holdings_digest =
                               NEW.current_holdings_digest
                     )
                THEN RAISE(
                    ABORT,
                    'canonical character holdings head does not exist'
                )
            END;
            SELECT CASE
                WHEN NEW.revision_state = 'canonical'
                     AND NOT EXISTS (
                         SELECT 1
                         FROM character_loadout_revisions AS loadout
                         WHERE loadout.character_id = NEW.character_id
                           AND loadout.loadout_revision =
                               NEW.current_loadout_revision
                           AND loadout.loadout_digest =
                               NEW.current_loadout_digest
                           AND loadout.based_on_definition_revision =
                               NEW.current_definition_revision
                     )
                THEN RAISE(
                    ABORT,
                    'canonical character loadout head does not exist'
                )
            END;
        END
        """,
        """
        CREATE TRIGGER characters_revision_heads_update_guard
        BEFORE UPDATE OF
            revision_state,
            current_definition_revision,
            current_definition_digest,
            current_holdings_revision,
            current_holdings_digest,
            current_loadout_revision,
            current_loadout_digest
        ON characters
        BEGIN
            SELECT CASE
                WHEN NEW.revision_state = 'legacy_pending'
                     AND (
                         NEW.current_definition_revision IS NOT NULL
                         OR NEW.current_definition_digest IS NOT NULL
                         OR NEW.current_holdings_revision IS NOT NULL
                         OR NEW.current_holdings_digest IS NOT NULL
                         OR NEW.current_loadout_revision IS NOT NULL
                         OR NEW.current_loadout_digest IS NOT NULL
                     )
                THEN RAISE(
                    ABORT,
                    'legacy-pending characters cannot have revision heads'
                )
                WHEN NEW.revision_state = 'canonical'
                     AND (
                         NEW.current_definition_revision IS NULL
                         OR NEW.current_definition_digest IS NULL
                         OR NEW.current_holdings_revision IS NULL
                         OR NEW.current_holdings_digest IS NULL
                         OR NEW.current_loadout_revision IS NULL
                         OR NEW.current_loadout_digest IS NULL
                     )
                THEN RAISE(
                    ABORT,
                    'canonical characters require complete revision heads'
                )
            END;
            SELECT CASE
                WHEN NEW.revision_state = 'canonical'
                     AND NOT EXISTS (
                         SELECT 1
                         FROM character_definitions AS definition
                         WHERE definition.character_id = NEW.character_id
                           AND definition.definition_revision =
                               NEW.current_definition_revision
                           AND definition.definition_digest =
                               NEW.current_definition_digest
                     )
                THEN RAISE(
                    ABORT,
                    'canonical character definition head does not exist'
                )
            END;
            SELECT CASE
                WHEN NEW.revision_state = 'canonical'
                     AND NOT EXISTS (
                         SELECT 1
                         FROM character_holdings_revisions AS holdings
                         WHERE holdings.character_id = NEW.character_id
                           AND holdings.holdings_revision =
                               NEW.current_holdings_revision
                           AND holdings.holdings_digest =
                               NEW.current_holdings_digest
                     )
                THEN RAISE(
                    ABORT,
                    'canonical character holdings head does not exist'
                )
            END;
            SELECT CASE
                WHEN NEW.revision_state = 'canonical'
                     AND NOT EXISTS (
                         SELECT 1
                         FROM character_loadout_revisions AS loadout
                         WHERE loadout.character_id = NEW.character_id
                           AND loadout.loadout_revision =
                               NEW.current_loadout_revision
                           AND loadout.loadout_digest =
                               NEW.current_loadout_digest
                           AND loadout.based_on_definition_revision =
                               NEW.current_definition_revision
                     )
                THEN RAISE(
                    ABORT,
                    'canonical character loadout head does not exist'
                )
            END;
            SELECT CASE
                WHEN OLD.revision_state = 'canonical'
                     AND NEW.revision_state != 'canonical'
                THEN RAISE(
                    ABORT,
                    'canonical characters cannot become legacy pending'
                )
            END;
            SELECT CASE
                WHEN OLD.revision_state = 'canonical'
                     AND (
                         NEW.current_definition_revision <
                             OLD.current_definition_revision
                         OR NEW.current_holdings_revision <
                             OLD.current_holdings_revision
                         OR NEW.current_loadout_revision <
                             OLD.current_loadout_revision
                     )
                THEN RAISE(
                    ABORT,
                    'canonical character revision heads cannot move backward'
                )
            END;
        END
        """,
        """
        CREATE TRIGGER character_deployment_pins_insert_guard
        BEFORE INSERT ON character_deployments
        BEGIN
            SELECT CASE
                WHEN NEW.pin_state = 'legacy_pending'
                     AND (
                         NEW.lease_id IS NOT NULL
                         OR NEW.definition_revision IS NOT NULL
                         OR NEW.definition_digest IS NOT NULL
                         OR NEW.holdings_revision IS NOT NULL
                         OR NEW.holdings_digest IS NOT NULL
                         OR NEW.loadout_revision IS NOT NULL
                         OR NEW.loadout_digest IS NOT NULL
                     )
                THEN RAISE(
                    ABORT,
                    'legacy-pending deployments cannot have revision pins'
                )
                WHEN NEW.pin_state = 'pinned'
                     AND (
                         NEW.lease_id IS NULL
                         OR NEW.definition_revision IS NULL
                         OR NEW.definition_digest IS NULL
                         OR NEW.holdings_revision IS NULL
                         OR NEW.holdings_digest IS NULL
                         OR NEW.loadout_revision IS NULL
                         OR NEW.loadout_digest IS NULL
                     )
                THEN RAISE(
                    ABORT,
                    'pinned deployments require complete revision pins'
                )
            END;
            SELECT CASE
                WHEN NEW.pin_state = 'pinned'
                     AND NOT EXISTS (
                         SELECT 1
                         FROM character_deployment_leases AS lease
                         WHERE lease.lease_id = NEW.lease_id
                           AND lease.character_id = NEW.character_id
                           AND lease.game_id = NEW.game_id
                           AND lease.membership_id = NEW.membership_id
                           AND lease.released_at IS NULL
                     )
                THEN RAISE(
                    ABORT,
                    'pinned deployment requires its active character lease'
                )
            END;
            SELECT CASE
                WHEN NEW.pin_state = 'pinned'
                     AND NOT EXISTS (
                         SELECT 1
                         FROM characters AS character
                         WHERE character.character_id = NEW.character_id
                           AND character.revision_state = 'canonical'
                           AND character.current_definition_revision =
                               NEW.definition_revision
                           AND character.current_definition_digest =
                               NEW.definition_digest
                           AND character.current_holdings_revision =
                               NEW.holdings_revision
                           AND character.current_holdings_digest =
                               NEW.holdings_digest
                           AND character.current_loadout_revision =
                               NEW.loadout_revision
                           AND character.current_loadout_digest =
                               NEW.loadout_digest
                     )
                THEN RAISE(
                    ABORT,
                    'deployment pins do not match current character heads'
                )
            END;
        END
        """,
        """
        CREATE TRIGGER character_deployments_immutable_update
        BEFORE UPDATE OF
            deployment_id,
            game_id,
            membership_id,
            character_id,
            entity_uuid,
            deployed_at,
            lease_id,
            pin_state,
            definition_revision,
            definition_digest,
            holdings_revision,
            holdings_digest,
            loadout_revision,
            loadout_digest
        ON character_deployments
        BEGIN
            SELECT RAISE(
                ABORT,
                'character deployment identity and revision lineage are immutable'
            );
        END
        """,
        """
        CREATE TRIGGER character_settlements_insert_guard
        BEFORE INSERT ON character_settlements
        WHEN NOT EXISTS (
            SELECT 1
            FROM character_deployments AS deployment
            JOIN games AS game
              ON game.game_id = deployment.game_id
            JOIN characters AS character
              ON character.character_id = deployment.character_id
            JOIN character_holdings_revisions AS starting
              ON starting.character_id = character.character_id
             AND starting.holdings_revision =
                 NEW.starting_holdings_revision
             AND starting.holdings_digest =
                 NEW.starting_holdings_digest
            JOIN character_holdings_revisions AS resulting
              ON resulting.character_id = character.character_id
             AND resulting.holdings_revision =
                 NEW.resulting_holdings_revision
             AND resulting.holdings_digest =
                 NEW.resulting_holdings_digest
            WHERE deployment.deployment_id = NEW.deployment_id
              AND deployment.game_id = NEW.game_id
              AND deployment.character_id = NEW.character_id
              AND deployment.pin_state = 'pinned'
              AND game.lifecycle_state = 'ended'
              AND deployment.holdings_revision =
                  NEW.starting_holdings_revision
              AND deployment.holdings_digest =
                  NEW.starting_holdings_digest
              AND character.current_holdings_revision =
                  NEW.resulting_holdings_revision
              AND character.current_holdings_digest =
                  NEW.resulting_holdings_digest
        )
        BEGIN
            SELECT RAISE(
                ABORT,
                'character settlement does not match deployment and holdings'
            );
        END
        """,
    ),
)

LOCAL_GAME_EXECUTION = Migration(
    version=6,
    name="local_game_execution",
    requires_foreign_keys_disabled=True,
    requires_legacy_alter_table=True,
    statements=(
        "ALTER TABLE games RENAME TO games_without_local_execution",
        """
        CREATE TABLE games (
            game_id TEXT PRIMARY KEY,
            engine_game_id TEXT,
            worker_id TEXT REFERENCES workers(worker_id),
            worker_generation INTEGER
                CHECK (worker_generation IS NULL OR worker_generation >= 1),
            created_by_principal_id TEXT NOT NULL
                REFERENCES principals(principal_id),
            lifecycle_state TEXT NOT NULL
                CHECK (
                    lifecycle_state IN (
                        'reserved',
                        'starting',
                        'active',
                        'ended',
                        'failed',
                        'interrupted',
                        'archived'
                    )
                ),
            visibility_policy TEXT NOT NULL
                CHECK (
                    visibility_policy IN ('public', 'unlisted', 'private')
                ),
            observer_policy TEXT NOT NULL
                CHECK (
                    observer_policy IN ('public', 'members', 'disabled')
                ),
            execution_kind TEXT NOT NULL
                CHECK (
                    execution_kind IN (
                        'hosted',
                        'local',
                        'evaluation',
                        'imported'
                    )
                ),
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
            final_event_cursor INTEGER
                CHECK (
                    final_event_cursor IS NULL OR final_event_cursor >= 0
                ),
            final_combat_log_cursor INTEGER
                CHECK (
                    final_combat_log_cursor IS NULL
                    OR final_combat_log_cursor >= 0
                ),
            current_summary_digest TEXT,
            row_version INTEGER NOT NULL DEFAULT 1
                CHECK (row_version >= 1),
            CHECK ((worker_id IS NULL) = (worker_generation IS NULL))
        )
        """,
        """
        INSERT INTO games(
            game_id,
            engine_game_id,
            worker_id,
            worker_generation,
            created_by_principal_id,
            lifecycle_state,
            visibility_policy,
            observer_policy,
            execution_kind,
            scenario_kind,
            scenario_id,
            display_name,
            creation_manifest_json,
            creation_manifest_digest,
            seed,
            ruleset_version,
            engine_version,
            content_digest,
            created_at,
            started_at,
            ended_at,
            archived_at,
            terminal_reason,
            winner_side_id,
            final_event_cursor,
            final_combat_log_cursor,
            current_summary_digest,
            row_version
        )
        SELECT
            game_id,
            engine_game_id,
            worker_id,
            worker_generation,
            created_by_principal_id,
            lifecycle_state,
            visibility_policy,
            observer_policy,
            execution_kind,
            scenario_kind,
            scenario_id,
            display_name,
            creation_manifest_json,
            creation_manifest_digest,
            seed,
            ruleset_version,
            engine_version,
            content_digest,
            created_at,
            started_at,
            ended_at,
            archived_at,
            terminal_reason,
            winner_side_id,
            final_event_cursor,
            final_combat_log_cursor,
            current_summary_digest,
            row_version
        FROM games_without_local_execution
        """,
        "DROP TABLE games_without_local_execution",
        """
        CREATE INDEX games_lifecycle_created_idx
        ON games(lifecycle_state, created_at)
        """,
        """
        CREATE INDEX games_worker_idx
        ON games(worker_id, worker_generation)
        """,
    ),
)

SCHEMA2_CHARACTER_DEFINITIONS = Migration(
    version=7,
    name="schema2_character_definitions",
    requires_foreign_keys_disabled=True,
    requires_legacy_alter_table=True,
    statements=(
        """
        ALTER TABLE character_definitions
        RENAME TO character_definitions_schema1
        """,
        """
        CREATE TABLE character_definitions (
            character_id TEXT NOT NULL
                REFERENCES characters(character_id),
            definition_revision INTEGER NOT NULL
                CHECK (definition_revision >= 1),
            schema_version INTEGER NOT NULL
                CHECK (schema_version IN (1, 2)),
            definition_json TEXT NOT NULL,
            definition_digest TEXT NOT NULL
                CHECK (
                    length(definition_digest) = 64
                    AND definition_digest NOT GLOB '*[^0-9a-f]*'
                ),
            created_at TEXT NOT NULL,
            PRIMARY KEY (character_id, definition_revision),
            UNIQUE (character_id, definition_digest)
        )
        """,
        """
        INSERT INTO character_definitions(
            character_id,
            definition_revision,
            schema_version,
            definition_json,
            definition_digest,
            created_at
        )
        SELECT
            character_id,
            definition_revision,
            schema_version,
            definition_json,
            definition_digest,
            created_at
        FROM character_definitions_schema1
        """,
        "DROP TABLE character_definitions_schema1",
        """
        CREATE TRIGGER character_definitions_immutable_update
        BEFORE UPDATE ON character_definitions
        BEGIN
            SELECT RAISE(
                ABORT,
                'character definition revisions are immutable'
            );
        END
        """,
        """
        CREATE TRIGGER character_definitions_immutable_delete
        BEFORE DELETE ON character_definitions
        BEGIN
            SELECT RAISE(
                ABORT,
                'character definition revisions are immutable'
            );
        END
        """,
    ),
)

DIRECTORY_MUTATION_RECEIPTS = Migration(
    version=8,
    name="directory_mutation_receipts",
    statements=(
        """
        CREATE TABLE directory_mutation_receipts (
            owner_principal_id TEXT NOT NULL
                REFERENCES principals(principal_id),
            idempotency_key TEXT NOT NULL,
            operation_kind TEXT NOT NULL
                CHECK (
                    length(operation_kind) BETWEEN 1 AND 80
                    AND operation_kind NOT GLOB '*[^a-z0-9_.-]*'
                ),
            scope_id TEXT NOT NULL,
            request_digest TEXT NOT NULL
                CHECK (
                    length(request_digest) = 64
                    AND request_digest NOT GLOB '*[^0-9a-f]*'
                ),
            result_payload_json TEXT NOT NULL,
            result_digest TEXT NOT NULL
                CHECK (
                    length(result_digest) = 64
                    AND result_digest NOT GLOB '*[^0-9a-f]*'
                ),
            created_at TEXT NOT NULL,
            PRIMARY KEY (owner_principal_id, idempotency_key)
        )
        """,
        """
        CREATE INDEX directory_mutation_receipts_scope_idx
        ON directory_mutation_receipts(scope_id, operation_kind, created_at)
        """,
        """
        CREATE TRIGGER directory_mutation_receipts_immutable_update
        BEFORE UPDATE ON directory_mutation_receipts
        BEGIN
            SELECT RAISE(
                ABORT,
                'directory mutation receipts are immutable'
            );
        END
        """,
        """
        CREATE TRIGGER directory_mutation_receipts_immutable_delete
        BEFORE DELETE ON directory_mutation_receipts
        BEGIN
            SELECT RAISE(
                ABORT,
                'directory mutation receipts are immutable'
            );
        END
        """,
    ),
)

LOCAL_TERMINAL_COMMIT_INTENTS = Migration(
    version=9,
    name="local_terminal_commit_intents",
    statements=(
        """
        CREATE TABLE local_terminal_commit_intents (
            game_id TEXT PRIMARY KEY REFERENCES games(game_id),
            lease_id TEXT REFERENCES character_deployment_leases(lease_id),
            payload_json TEXT NOT NULL,
            payload_digest TEXT NOT NULL
                CHECK (
                    length(payload_digest) = 64
                    AND payload_digest NOT GLOB '*[^0-9a-f]*'
                ),
            staged_at TEXT NOT NULL,
            committed_at TEXT
        )
        """,
        """
        CREATE INDEX local_terminal_commit_intents_state_idx
        ON local_terminal_commit_intents(committed_at, staged_at)
        """,
    ),
)

WORKER_TERMINAL_READY_MANIFESTS = Migration(
    version=10,
    name="worker_terminal_ready_manifests",
    statements=(
        """
        CREATE TABLE worker_terminal_ready_manifests (
            game_id TEXT PRIMARY KEY REFERENCES games(game_id),
            worker_id TEXT NOT NULL REFERENCES workers(worker_id),
            worker_generation INTEGER NOT NULL
                CHECK (worker_generation >= 1),
            objective_artifact_json TEXT NOT NULL,
            subjective_artifact_json TEXT NOT NULL,
            summary_evidence_json TEXT NOT NULL,
            settlement_evidence_json TEXT,
            manifest_digest TEXT NOT NULL
                CHECK (
                    length(manifest_digest) = 64
                    AND manifest_digest NOT GLOB '*[^0-9a-f]*'
                ),
            ready_at TEXT NOT NULL,
            staged_at TEXT NOT NULL,
            adopted_at TEXT,
            UNIQUE(worker_id, worker_generation, manifest_digest)
        )
        """,
        """
        CREATE INDEX worker_terminal_ready_manifests_state_idx
        ON worker_terminal_ready_manifests(adopted_at, ready_at)
        """,
        """
        CREATE TRIGGER worker_terminal_ready_manifests_identity_immutable
        BEFORE UPDATE OF
            game_id,
            worker_id,
            worker_generation,
            objective_artifact_json,
            subjective_artifact_json,
            summary_evidence_json,
            settlement_evidence_json,
            manifest_digest,
            ready_at,
            staged_at
        ON worker_terminal_ready_manifests
        BEGIN
            SELECT RAISE(
                ABORT,
                'worker terminal ready manifest identity is immutable'
            );
        END
        """,
        """
        CREATE TRIGGER worker_terminal_ready_manifests_adoption_once
        BEFORE UPDATE OF adopted_at ON worker_terminal_ready_manifests
        WHEN OLD.adopted_at IS NOT NULL OR NEW.adopted_at IS NULL
        BEGIN
            SELECT RAISE(
                ABORT,
                'worker terminal ready manifest adoption is one-way'
            );
        END
        """,
        """
        CREATE TRIGGER worker_terminal_ready_manifests_immutable_delete
        BEFORE DELETE ON worker_terminal_ready_manifests
        BEGIN
            SELECT RAISE(
                ABORT,
                'worker terminal ready manifests are immutable'
            );
        END
        """,
    ),
)

CHARACTER_PRESENTATION_PREFERENCES = Migration(
    version=11,
    name="character_presentation_preferences",
    statements=(
        """
        CREATE TABLE character_presentation_preferences (
            character_id TEXT PRIMARY KEY
                REFERENCES characters(character_id) ON DELETE CASCADE,
            schema_version INTEGER NOT NULL
                CHECK (schema_version = 1),
            preferences_json TEXT NOT NULL,
            preferences_digest TEXT NOT NULL
                CHECK (
                    length(preferences_digest) = 64
                    AND preferences_digest NOT GLOB '*[^0-9a-f]*'
                ),
            revision INTEGER NOT NULL
                CHECK (revision >= 1),
            updated_at TEXT NOT NULL
        )
        """,
    ),
)

ROSTERS_ENCOUNTERS_AND_PLURAL_DEPLOYMENTS = Migration(
    version=12,
    name="rosters_encounters_and_plural_deployments",
    statements=(
        """
        ALTER TABLE local_terminal_commit_intents
        ADD COLUMN lease_ids_json TEXT NOT NULL DEFAULT '[]'
        """,
        """
        UPDATE local_terminal_commit_intents
        SET lease_ids_json = CASE
            WHEN lease_id IS NULL THEN '[]'
            ELSE '["' || lease_id || '"]'
        END
        """,
        """
        CREATE TABLE saved_encounter_rosters (
            roster_id TEXT PRIMARY KEY,
            owner_principal_id TEXT NOT NULL
                REFERENCES principals(principal_id),
            schema_version INTEGER NOT NULL CHECK (schema_version = 1),
            title TEXT NOT NULL,
            recipe_json TEXT NOT NULL,
            recipe_digest TEXT NOT NULL
                CHECK (
                    length(recipe_digest) = 64
                    AND recipe_digest NOT GLOB '*[^0-9a-f]*'
                ),
            revision INTEGER NOT NULL CHECK (revision >= 1),
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE(owner_principal_id, title)
        )
        """,
        """
        CREATE INDEX saved_encounter_rosters_owner_idx
        ON saved_encounter_rosters(owner_principal_id, updated_at, roster_id)
        """,
        """
        CREATE TABLE saved_encounters (
            encounter_id TEXT PRIMARY KEY,
            owner_principal_id TEXT NOT NULL
                REFERENCES principals(principal_id),
            schema_version INTEGER NOT NULL CHECK (schema_version = 1),
            title TEXT NOT NULL,
            recipe_json TEXT NOT NULL,
            recipe_digest TEXT NOT NULL
                CHECK (
                    length(recipe_digest) = 64
                    AND recipe_digest NOT GLOB '*[^0-9a-f]*'
                ),
            revision INTEGER NOT NULL CHECK (revision >= 1),
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE(owner_principal_id, title)
        )
        """,
        """
        CREATE INDEX saved_encounters_owner_idx
        ON saved_encounters(owner_principal_id, updated_at, encounter_id)
        """,
    ),
)

STABLE_SAVED_RESOURCE_IDENTITIES = Migration(
    version=13,
    name="stable_saved_resource_identities",
    statements=(
        """
        ALTER TABLE saved_encounter_rosters
        RENAME COLUMN roster_id TO saved_roster_id
        """,
        """
        ALTER TABLE saved_encounters
        RENAME COLUMN encounter_id TO saved_encounter_id
        """,
    ),
)

REMOVE_ABANDONED_RATING_STORAGE = Migration(
    version=14,
    name="remove_abandoned_rating_storage",
    statements=(
        "DROP TABLE IF EXISTS rating_estimates",
        "DROP TABLE IF EXISTS rating_admissions",
        "DROP TABLE IF EXISTS rating_runs",
    ),
)

MIGRATIONS: tuple[Migration, ...] = (
    INITIAL_SCHEMA,
    PLAYER_IDENTITIES_AND_CHARACTERS,
    SUBJECTIVE_REPLAY_ARTIFACT,
    CHARACTER_REVISIONS_AND_DEPLOYMENT_LEASES,
    CHARACTER_PROFILE_PROGRESSION_FOUNDATION,
    LOCAL_GAME_EXECUTION,
    SCHEMA2_CHARACTER_DEFINITIONS,
    DIRECTORY_MUTATION_RECEIPTS,
    LOCAL_TERMINAL_COMMIT_INTENTS,
    WORKER_TERMINAL_READY_MANIFESTS,
    CHARACTER_PRESENTATION_PREFERENCES,
    ROSTERS_ENCOUNTERS_AND_PLURAL_DEPLOYMENTS,
    STABLE_SAVED_RESOURCE_IDENTITIES,
    REMOVE_ABANDONED_RATING_STORAGE,
)
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
        if (
            migration.version
            == CHARACTER_PROFILE_PROGRESSION_FOUNDATION.version
            and _canonical_character_count(connection) > 0
        ):
            raise MigrationError(
                f"{OFFLINE_CHARACTER_LOADOUT_BACKFILL_REQUIRED}: "
                "run the audited game-directory character loadout backfill "
                "before normal startup",
            )
        foreign_keys_temporarily_disabled = False
        original_legacy_alter_table = int(
            connection.execute("PRAGMA legacy_alter_table").fetchone()[0]
        )
        if migration.requires_foreign_keys_disabled:
            if connection.in_transaction:
                raise MigrationError(
                    f"Migration {migration.version} ({migration.name}) requires "
                    "an autocommit connection before disabling foreign keys"
                )
            connection.execute("PRAGMA foreign_keys = OFF")
            foreign_keys_temporarily_disabled = True
            if int(connection.execute("PRAGMA foreign_keys").fetchone()[0]) != 0:
                raise MigrationError(
                    f"Migration {migration.version} ({migration.name}) could "
                    "not disable foreign-key enforcement"
                )
        if migration.requires_legacy_alter_table:
            connection.execute("PRAGMA legacy_alter_table = ON")
            if int(connection.execute("PRAGMA legacy_alter_table").fetchone()[0]) != 1:
                if foreign_keys_temporarily_disabled:
                    connection.execute("PRAGMA foreign_keys = ON")
                raise MigrationError(
                    f"Migration {migration.version} ({migration.name}) could "
                    "not enable legacy table-rename behavior"
                )
        connection.execute("BEGIN IMMEDIATE")
        try:
            for statement in migration.statements:
                connection.execute(statement)
            if migration.requires_foreign_keys_disabled:
                violations = connection.execute("PRAGMA foreign_key_check").fetchall()
                if violations:
                    raise sqlite3.IntegrityError(
                        f"foreign-key check failed with {len(violations)} violation(s)"
                    )
            connection.execute(
                "INSERT INTO schema_migrations(version, name, checksum, applied_at) VALUES (?, ?, ?, ?)",
                (migration.version, migration.name, migration.checksum, timestamp),
            )
            connection.execute("COMMIT")
        except sqlite3.Error as exc:
            if connection.in_transaction:
                connection.execute("ROLLBACK")
            raise MigrationError(
                f"Failed to apply migration {migration.version} ({migration.name}): {exc}"
            ) from exc
        finally:
            try:
                if migration.requires_legacy_alter_table:
                    connection.execute(
                        f"PRAGMA legacy_alter_table = {original_legacy_alter_table}"
                    )
                    restored_legacy_alter_table = int(
                        connection.execute("PRAGMA legacy_alter_table").fetchone()[0]
                    )
                    if restored_legacy_alter_table != original_legacy_alter_table:
                        raise MigrationError(
                            f"Migration {migration.version} ({migration.name}) "
                            "could not restore table-rename behavior"
                        )
            finally:
                if foreign_keys_temporarily_disabled:
                    connection.execute("PRAGMA foreign_keys = ON")
                    if (
                        int(connection.execute("PRAGMA foreign_keys").fetchone()[0])
                        != 1
                    ):
                        raise MigrationError(
                            f"Migration {migration.version} ({migration.name}) "
                            "could not restore foreign-key enforcement"
                        )

    return migrations[-1].version if migrations else 0


def _canonical_character_count(connection: sqlite3.Connection) -> int:
    """Return existing two-head canonical rows before the loadout hard cut."""

    table = connection.execute(
        """
        SELECT 1 FROM sqlite_master
        WHERE type = 'table' AND name = 'characters'
        """,
    ).fetchone()
    if table is None:
        return 0
    columns = {
        row["name"]
        for row in connection.execute("PRAGMA table_info(characters)").fetchall()
    }
    if "revision_state" not in columns:
        return 0
    return int(
        connection.execute(
            "SELECT COUNT(*) FROM characters WHERE revision_state = 'canonical'",
        ).fetchone()[0],
    )
