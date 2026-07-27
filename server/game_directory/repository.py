"""Transactional repository for the typed SQLite game directory."""

from __future__ import annotations

import hmac
import json
import secrets
import sqlite3
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

from pydantic import JsonValue, TypeAdapter, ValidationError

from dnd.analytics.models import GameSummary, summary_digest_is_valid
from dnd.core.content.durable_characters import (
    CharacterDefinitionRevisionV2,
    CharacterHoldingsRevision,
    CharacterLoadoutRevisionV1,
)

from server.game_directory.canonical import (
    canonical_digest,
    canonical_json,
    datetime_to_text,
    hash_capability,
    utc_now,
)
from server.game_directory.contracts import (
    AccessGrantCreate,
    AccessGrantRecord,
    ArtifactCreate,
    ArtifactKind,
    ArtifactRecord,
    AttachmentCreate,
    AttachmentRecord,
    AttachmentState,
    CanonicalCharacterRecord,
    CharacterAdvancementAwardCreate,
    CharacterAdvancementAwardRecord,
    CharacterBootstrapCreate,
    CharacterDefinitionRecord,
    CharacterDeploymentLeaseCreate,
    CharacterDeploymentLeaseRecord,
    CharacterHoldingsRecord,
    CharacterLoadoutRecord,
    CharacterRecord,
    CharacterRevisionBundleCommit,
    CharacterRevisionHeads,
    CharacterRevisionState,
    CharacterSettlementRecord,
    DirectoryEventRecord,
    DirectoryMutationReceiptRecord,
    EntityAssignmentCreate,
    EntityAssignmentRecord,
    FinalSummaryRecord,
    GameCreate,
    GameLifecycleState,
    GameRecord,
    IssuedAccessGrant,
    IssuedAttachment,
    MembershipCapabilities,
    MembershipCreate,
    MembershipRecord,
    MembershipState,
    PinnedCharacterDeploymentCreate,
    PinnedCharacterDeploymentRecord,
    PlayerIdentityRecord,
    PrincipalCreate,
    PrincipalCredentialCreate,
    PrincipalCredentialRecord,
    PrincipalRecord,
    ProfileSettingsCreate,
    ProfileSettingsRecord,
    ProfileSettingsUpdate,
    RatingAdmissionCreate,
    RatingAdmissionRecord,
    RatingEstimateCreate,
    RatingEstimateRecord,
    RatingRunCreate,
    RatingRunRecord,
    RatingRunStatus,
    RepositoryMetrics,
    WorkerCreate,
    WorkerRecord,
    WorkerState,
    WorkerTerminalReadyManifestCreate,
    WorkerTerminalReadyManifestRecord,
)

from server.game_directory.database import DirectoryDatabase
from server.game_directory.errors import (
    CapabilityError,
    ConflictError,
    ImmutableRecordError,
    NotFoundError,
    StaleVersionError,
)

_GAME_SUMMARY_ADAPTER = TypeAdapter(GameSummary)
_CHARACTER_DEFINITION_ADAPTER = TypeAdapter(CharacterDefinitionRevisionV2)
JsonObject = dict[str, JsonValue]


def _load_json_object(value: str) -> JsonObject:
    """Decode one persisted canonical JSON object."""

    decoded = json.loads(value)
    if not isinstance(decoded, dict):
        raise ValueError("Persisted directory JSON must be an object")
    return decoded


def _load_canonical_json_object(value: str, record_name: str) -> JsonObject:
    """Decode one object only when its persisted bytes are canonical JSON."""

    decoded = _load_json_object(value)
    if canonical_json(decoded) != value:
        raise ImmutableRecordError(
            f"Persisted {record_name} JSON is not canonical",
        )
    return decoded


def _optional_text(value: datetime | None) -> str | None:
    """Serialize an optional UTC timestamp for SQLite."""

    return datetime_to_text(value) if value is not None else None


def _principal_from_row(row: sqlite3.Row) -> PrincipalRecord:
    """Build a typed principal from one SQLite row."""

    return PrincipalRecord(
        principal_id=row["principal_id"],
        principal_kind=row["principal_kind"],
        display_name=row["display_name"],
        credential_hash=row["credential_hash"],
        metadata=_load_json_object(row["metadata_json"]),
        metadata_digest=row["metadata_digest"],
        created_at=row["created_at"],
        last_seen_at=row["last_seen_at"],
        disabled_at=row["disabled_at"],
    )


def _player_identity_from_row(row: sqlite3.Row) -> PlayerIdentityRecord:
    """Build one durable name identity from a SQLite row."""

    return PlayerIdentityRecord(
        identity_key=row["identity_key"],
        principal_id=row["principal_id"],
        display_name=row["identity_display_name"],
        created_at=row["identity_created_at"],
    )


def _principal_credential_from_row(row: sqlite3.Row) -> PrincipalCredentialRecord:
    """Build one independently revocable principal credential."""

    return PrincipalCredentialRecord(
        credential_id=row["credential_id"],
        principal_id=row["principal_id"],
        client_instance_id=row["client_instance_id"],
        secret_hash=row["secret_hash"],
        issued_at=row["issued_at"],
        last_seen_at=row["last_seen_at"],
        revoked_at=row["revoked_at"],
    )


def _character_from_row(row: sqlite3.Row) -> CharacterRecord:
    """Build one persistent character from a SQLite row."""

    return CharacterRecord(
        character_id=row["character_id"],
        owner_principal_id=row["owner_principal_id"],
        display_name=row["display_name"],
        status=row["status"],
        revision_state=row["revision_state"],
        current_definition_revision=row["current_definition_revision"],
        current_definition_digest=row["current_definition_digest"],
        current_holdings_revision=row["current_holdings_revision"],
        current_holdings_digest=row["current_holdings_digest"],
        current_loadout_revision=row["current_loadout_revision"],
        current_loadout_digest=row["current_loadout_digest"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        row_version=row["row_version"],
    )


def _canonical_character_from_row(row: sqlite3.Row) -> CanonicalCharacterRecord:
    """Build one character whose exact durable revision heads are installed."""

    return CanonicalCharacterRecord.model_validate(
        _character_from_row(row).model_dump(),
    )


def _character_definition_from_row(
    row: sqlite3.Row,
) -> CharacterDefinitionRecord:
    """Decode and authenticate one immutable structural character revision."""

    payload = _load_canonical_json_object(
        row["definition_json"],
        "character definition",
    )
    try:
        definition = _CHARACTER_DEFINITION_ADAPTER.validate_python(payload)
    except ValidationError as exc:
        raise ImmutableRecordError(
            "Persisted character definition failed durable integrity validation",
        ) from exc
    if (
        str(definition.character_id) != row["character_id"]
        or definition.definition_revision != row["definition_revision"]
        or definition.schema_version != row["schema_version"]
        or definition.definition_digest != row["definition_digest"]
    ):
        raise ImmutableRecordError(
            "Character definition row metadata does not match its canonical JSON",
        )
    return CharacterDefinitionRecord(
        definition=definition,
        created_at=row["created_at"],
    )


def _character_holdings_from_row(
    row: sqlite3.Row,
) -> CharacterHoldingsRecord:
    """Decode and authenticate one immutable holdings revision."""

    payload = _load_canonical_json_object(
        row["holdings_json"],
        "character holdings",
    )
    try:
        holdings = CharacterHoldingsRevision.model_validate(payload)
    except ValidationError as exc:
        raise ImmutableRecordError(
            "Persisted character holdings failed durable integrity validation",
        ) from exc
    if (
        str(holdings.character_id) != row["character_id"]
        or holdings.holdings_revision != row["holdings_revision"]
        or holdings.schema_version != row["schema_version"]
        or holdings.holdings_digest != row["holdings_digest"]
    ):
        raise ImmutableRecordError(
            "Character holdings row metadata does not match its canonical JSON",
        )
    return CharacterHoldingsRecord(
        holdings=holdings,
        created_at=row["created_at"],
    )


def _character_loadout_from_row(row: sqlite3.Row) -> CharacterLoadoutRecord:
    """Decode and authenticate one immutable loadout revision."""

    payload = _load_canonical_json_object(
        row["loadout_json"],
        "character loadout",
    )
    try:
        loadout = CharacterLoadoutRevisionV1.model_validate(payload)
    except ValidationError as exc:
        raise ImmutableRecordError(
            "Persisted character loadout failed durable integrity validation",
        ) from exc
    if (
        str(loadout.character_id) != row["character_id"]
        or loadout.loadout_revision != row["loadout_revision"]
        or loadout.schema_version != row["schema_version"]
        or loadout.based_on_definition_revision
        != row["based_on_definition_revision"]
        or loadout.loadout_digest != row["loadout_digest"]
    ):
        raise ImmutableRecordError(
            "Character loadout row metadata does not match its canonical JSON",
        )
    return CharacterLoadoutRecord(
        loadout=loadout,
        created_at=row["created_at"],
    )


def _profile_settings_from_row(row: sqlite3.Row) -> ProfileSettingsRecord:
    """Build one principal-owned rules policy record."""

    return ProfileSettingsRecord(
        owner_principal_id=row["owner_principal_id"],
        permissive_multiclass_prerequisites=bool(
            row["permissive_multiclass_prerequisites"],
        ),
        multiclass_slot_rounding_policy=row[
            "multiclass_slot_rounding_policy"
        ],
        allow_respec=bool(row["allow_respec"]),
        spell_preparation_policy=row["spell_preparation_policy"],
        settings_version=row["settings_version"],
        ruleset_digest=row["ruleset_digest"],
        updated_at=row["updated_at"],
    )


def _character_advancement_award_from_row(
    row: sqlite3.Row,
) -> CharacterAdvancementAwardRecord:
    """Build one immutable advancement authority row."""

    return CharacterAdvancementAwardRecord(
        award_id=row["award_id"],
        character_id=row["character_id"],
        level_delta=row["level_delta"],
        source_kind=row["source_kind"],
        source_id=row["source_id"],
        created_at=row["created_at"],
    )


def _character_settlement_from_row(
    row: sqlite3.Row,
) -> CharacterSettlementRecord:
    """Build one immutable exactly-once settlement receipt."""

    return CharacterSettlementRecord(
        settlement_id=row["settlement_id"],
        deployment_id=row["deployment_id"],
        game_id=row["game_id"],
        character_id=row["character_id"],
        starting_holdings_revision=row["starting_holdings_revision"],
        starting_holdings_digest=row["starting_holdings_digest"],
        resulting_holdings_revision=row["resulting_holdings_revision"],
        resulting_holdings_digest=row["resulting_holdings_digest"],
        delta_digest=row["delta_digest"],
        settled_at=row["settled_at"],
    )


def _directory_mutation_receipt_from_row(
    row: sqlite3.Row,
) -> DirectoryMutationReceiptRecord:
    """Decode and authenticate one immutable directory mutation receipt."""

    payload = _load_canonical_json_object(
        row["result_payload_json"],
        "directory mutation receipt result",
    )
    return DirectoryMutationReceiptRecord(
        owner_principal_id=row["owner_principal_id"],
        idempotency_key=row["idempotency_key"],
        operation_kind=row["operation_kind"],
        scope_id=row["scope_id"],
        request_digest=row["request_digest"],
        result_payload=payload,
        result_digest=row["result_digest"],
        created_at=row["created_at"],
    )


def _pinned_character_deployment_from_row(
    row: sqlite3.Row,
) -> PinnedCharacterDeploymentRecord:
    """Build one deployment whose durable revision pins are complete."""

    return PinnedCharacterDeploymentRecord(
        deployment_id=row["deployment_id"],
        game_id=row["game_id"],
        membership_id=row["membership_id"],
        character_id=row["character_id"],
        entity_uuid=row["entity_uuid"],
        lease_id=row["lease_id"],
        pin_state=row["pin_state"],
        definition_revision=row["definition_revision"],
        definition_digest=row["definition_digest"],
        holdings_revision=row["holdings_revision"],
        holdings_digest=row["holdings_digest"],
        loadout_revision=row["loadout_revision"],
        loadout_digest=row["loadout_digest"],
        deployed_at=row["deployed_at"],
    )


def _character_deployment_lease_from_row(
    row: sqlite3.Row,
) -> CharacterDeploymentLeaseRecord:
    """Build one exclusive character deployment lease."""

    return CharacterDeploymentLeaseRecord(
        lease_id=row["lease_id"],
        character_id=row["character_id"],
        game_id=row["game_id"],
        membership_id=row["membership_id"],
        acquired_at=row["acquired_at"],
        released_at=row["released_at"],
        release_reason=row["release_reason"],
    )


def _worker_from_row(row: sqlite3.Row) -> WorkerRecord:
    """Build a typed worker from one SQLite row."""

    return WorkerRecord(
        worker_id=row["worker_id"],
        worker_generation=row["worker_generation"],
        state=row["state"],
        pid=row["pid"],
        process_group_id=row["process_group_id"],
        host_id=row["host_id"],
        transport_kind=row["transport_kind"],
        private_locator=row["private_locator"],
        lease_expires_at=row["lease_expires_at"],
        protocol_hash=row["protocol_hash"],
        engine_version=row["engine_version"],
        started_at=row["started_at"],
        last_heartbeat_at=row["last_heartbeat_at"],
        stopped_at=row["stopped_at"],
        failure_code=row["failure_code"],
        failure_detail=_load_json_object(row["failure_detail_json"]),
    )


def _game_from_row(row: sqlite3.Row) -> GameRecord:
    """Build a typed hosted game from one SQLite row."""

    return GameRecord(
        game_id=row["game_id"],
        engine_game_id=row["engine_game_id"],
        worker_id=row["worker_id"],
        worker_generation=row["worker_generation"],
        created_by_principal_id=row["created_by_principal_id"],
        lifecycle_state=row["lifecycle_state"],
        visibility_policy=row["visibility_policy"],
        observer_policy=row["observer_policy"],
        execution_kind=row["execution_kind"],
        scenario_kind=row["scenario_kind"],
        scenario_id=row["scenario_id"],
        display_name=row["display_name"],
        creation_manifest=_load_json_object(row["creation_manifest_json"]),
        creation_manifest_digest=row["creation_manifest_digest"],
        seed=row["seed"],
        ruleset_version=row["ruleset_version"],
        engine_version=row["engine_version"],
        content_digest=row["content_digest"],
        created_at=row["created_at"],
        started_at=row["started_at"],
        ended_at=row["ended_at"],
        archived_at=row["archived_at"],
        terminal_reason=row["terminal_reason"],
        winner_side_id=row["winner_side_id"],
        final_event_cursor=row["final_event_cursor"],
        final_combat_log_cursor=row["final_combat_log_cursor"],
        current_summary_digest=row["current_summary_digest"],
        row_version=row["row_version"],
    )


def _membership_from_row(row: sqlite3.Row) -> MembershipRecord:
    """Build a typed membership from one SQLite row."""

    capabilities = MembershipCapabilities(
        may_connect=bool(row["may_connect"]),
        may_observe_public_state=bool(row["may_observe_public_state"]),
        may_observe_subjective_state=bool(row["may_observe_subjective_state"]),
        may_control_entities=bool(row["may_control_entities"]),
        may_view_agent_telemetry=bool(row["may_view_agent_telemetry"]),
        may_manage_members=bool(row["may_manage_members"]),
        may_manage_game=bool(row["may_manage_game"]),
        may_view_objective_replay=bool(row["may_view_objective_replay"]),
    )
    return MembershipRecord(
        membership_id=row["membership_id"],
        game_id=row["game_id"],
        principal_id=row["principal_id"],
        role=row["role"],
        side_id=row["side_id"],
        controller_kind=row["controller_kind"],
        membership_state=row["membership_state"],
        capabilities=capabilities,
        subjective_source_membership_id=row["subjective_source_membership_id"],
        authority_epoch=row["authority_epoch"],
        joined_at=row["joined_at"],
        disconnected_at=row["disconnected_at"],
        revoked_at=row["revoked_at"],
        left_at=row["left_at"],
    )


def _assignment_from_row(row: sqlite3.Row) -> EntityAssignmentRecord:
    """Build a typed entity assignment from one SQLite row."""

    return EntityAssignmentRecord(
        assignment_id=row["assignment_id"],
        game_id=row["game_id"],
        membership_id=row["membership_id"],
        entity_uuid=row["entity_uuid"],
        entity_name=row["entity_name"],
        faction=row["faction"],
        side_id=row["side_id"],
        controller_kind=row["controller_kind"],
        authority_epoch=row["authority_epoch"],
        assigned_at=row["assigned_at"],
        released_at=row["released_at"],
    )


def _grant_from_row(row: sqlite3.Row) -> AccessGrantRecord:
    """Build a typed access grant from one SQLite row."""

    return AccessGrantRecord(
        grant_id=row["grant_id"],
        game_id=row["game_id"],
        membership_id=row["membership_id"],
        issued_to_principal_id=row["issued_to_principal_id"],
        grant_kind=row["grant_kind"],
        scope=_load_json_object(row["scope_json"]),
        expires_at=row["expires_at"],
        max_uses=row["max_uses"],
        issued_by_principal_id=row["issued_by_principal_id"],
        secret_hash=row["secret_hash"],
        scope_digest=row["scope_digest"],
        issued_at=row["issued_at"],
        revoked_at=row["revoked_at"],
        uses=row["uses"],
    )


def _attachment_from_row(row: sqlite3.Row) -> AttachmentRecord:
    """Build a typed attachment from one SQLite row."""

    return AttachmentRecord(
        attachment_id=row["attachment_id"],
        runtime_session_id=row["runtime_session_id"],
        game_id=row["game_id"],
        membership_id=row["membership_id"],
        worker_id=row["worker_id"],
        worker_generation=row["worker_generation"],
        client_kind=row["client_kind"],
        client_instance_id=row["client_instance_id"],
        expires_at=row["expires_at"],
        authority_epoch=row["authority_epoch"],
        state=row["state"],
        runtime_token_hash=row["runtime_token_hash"],
        connected_at=row["connected_at"],
        last_seen_at=row["last_seen_at"],
        disconnected_at=row["disconnected_at"],
        disconnect_reason=row["disconnect_reason"],
        last_event_cursor=row["last_event_cursor"],
        last_combat_log_cursor=row["last_combat_log_cursor"],
    )


def _event_from_row(row: sqlite3.Row) -> DirectoryEventRecord:
    """Build a typed directory event from one SQLite row."""

    return DirectoryEventRecord(
        cursor=row["cursor"],
        event_id=row["event_id"],
        game_id=row["game_id"],
        event_type=row["event_type"],
        payload=_load_json_object(row["payload_json"]),
        payload_digest=row["payload_digest"],
        created_at=row["created_at"],
    )


def _artifact_from_row(row: sqlite3.Row) -> ArtifactRecord:
    """Build a typed immutable artifact descriptor from one SQLite row."""

    return ArtifactRecord(
        artifact_id=row["artifact_id"],
        game_id=row["game_id"],
        artifact_kind=row["artifact_kind"],
        schema_version=row["schema_version"],
        media_type=row["media_type"],
        uri=row["uri"],
        byte_size=row["byte_size"],
        content_digest=row["content_digest"],
        producer_kind=row["producer_kind"],
        producer_version=row["producer_version"],
        created_at=row["created_at"],
    )


def _worker_terminal_ready_manifest_from_row(
    row: sqlite3.Row,
) -> WorkerTerminalReadyManifestRecord:
    """Decode one immutable hosted terminal ready-manifest row."""

    return WorkerTerminalReadyManifestRecord(
        game_id=row["game_id"],
        worker_id=row["worker_id"],
        worker_generation=row["worker_generation"],
        objective_artifact=ArtifactCreate.model_validate_json(
            row["objective_artifact_json"],
        ),
        subjective_artifact=ArtifactCreate.model_validate_json(
            row["subjective_artifact_json"],
        ),
        summary_evidence=_load_canonical_json_object(
            row["summary_evidence_json"],
            "worker terminal summary evidence",
        ),
        settlement_evidence=(
            _load_canonical_json_object(
                row["settlement_evidence_json"],
                "worker terminal settlement evidence",
            )
            if row["settlement_evidence_json"] is not None
            else None
        ),
        manifest_digest=row["manifest_digest"],
        ready_at=row["ready_at"],
        staged_at=row["staged_at"],
        adopted_at=row["adopted_at"],
    )


def _summary_from_row(row: sqlite3.Row) -> FinalSummaryRecord:
    """Build a typed immutable summary revision from one SQLite row."""

    return FinalSummaryRecord(
        summary_id=row["summary_id"],
        game_id=row["game_id"],
        schema_version=row["schema_version"],
        summary_revision=row["summary_revision"],
        summary=_GAME_SUMMARY_ADAPTER.validate_json(row["summary_json"]),
        summary_digest=row["summary_digest"],
        winner_side_id=row["winner_side_id"],
        terminal_reason=row["terminal_reason"],
        round_count=row["round_count"],
        turn_count=row["turn_count"],
        duration_ms=row["duration_ms"],
        source_event_digest=row["source_event_digest"],
        source_combat_log_digest=row["source_combat_log_digest"],
        created_at=row["created_at"],
        supersedes_summary_id=row["supersedes_summary_id"],
        is_current=bool(row["is_current"]),
    )


def _rating_run_from_row(row: sqlite3.Row) -> RatingRunRecord:
    """Build a typed rating run from one SQLite row."""

    return RatingRunRecord(
        rating_run_id=row["rating_run_id"],
        algorithm_id=row["algorithm_id"],
        algorithm_version=row["algorithm_version"],
        parameters=_load_json_object(row["parameters_json"]),
        selection_query=_load_json_object(row["selection_query_json"]),
        compatibility_constraints=_load_json_object(row["compatibility_constraints_json"]),
        parameters_digest=row["parameters_digest"],
        selection_query_digest=row["selection_query_digest"],
        compatibility_digest=row["compatibility_digest"],
        status=row["status"],
        created_at=row["created_at"],
        completed_at=row["completed_at"],
        output_artifact_digest=row["output_artifact_digest"],
    )


def _rating_admission_from_row(row: sqlite3.Row) -> RatingAdmissionRecord:
    """Build a typed immutable rating admission from one SQLite row."""

    return RatingAdmissionRecord(
        admission_id=row["admission_id"],
        rating_run_id=row["rating_run_id"],
        game_id=row["game_id"],
        summary_digest=row["summary_digest"],
        admitted=bool(row["admitted"]),
        exclusion_reason_code=row["exclusion_reason_code"],
        exclusion_detail=_load_json_object(row["exclusion_detail_json"]),
        treatment_id=row["treatment_id"],
        configuration_id=row["configuration_id"],
        weight=row["weight"],
        created_at=row["created_at"],
    )


def _rating_estimate_from_row(row: sqlite3.Row) -> RatingEstimateRecord:
    """Build a typed immutable rating estimate from one SQLite row."""

    return RatingEstimateRecord(
        estimate_id=row["estimate_id"],
        rating_run_id=row["rating_run_id"],
        subject_id=row["subject_id"],
        estimate=row["estimate"],
        uncertainty=row["uncertainty"],
        games=row["games"],
        wins=row["wins"],
        losses=row["losses"],
        draws=row["draws"],
        rank=row["rank"],
        diagnostics=_load_json_object(row["diagnostics_json"]),
        diagnostics_digest=row["diagnostics_digest"],
        created_at=row["created_at"],
    )


class GameDirectoryRepository:
    """Typed transactional control-plane repository.

    This repository is intentionally unsuitable for gameplay hot paths. Use
    :meth:`forbid_hot_path_access` and :meth:`inject_failures` to prove that
    runtime paths remain independent after their cold attachment handshake.
    """

    def __init__(
        self,
        path: str | Path,
        *,
        capability_pepper: bytes,
        busy_timeout_ms: int = 2_000,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        """Open a migrated game-directory repository.

        Args:
            path: SQLite database file path.
            capability_pepper: Server-held HMAC key for capability digests.
            busy_timeout_ms: Bounded SQLite lock wait in milliseconds.
            clock: Injectable UTC clock used for deterministic tests.

        Raises:
            ValueError: If the capability pepper is empty.
        """

        if not capability_pepper:
            raise ValueError("capability_pepper cannot be empty")
        self._clock = clock
        self._capability_pepper = bytes(capability_pepper)
        self._database = DirectoryDatabase(
            path,
            busy_timeout_ms=busy_timeout_ms,
            migration_time=self._now(),
        )

    def close(self) -> None:
        """Close the repository idempotently."""

        self._database.close()

    def metrics(self) -> RepositoryMetrics:
        """Return repository-operation instrumentation."""

        return self._database.metrics()

    def reset_metrics(self) -> None:
        """Reset repository-operation instrumentation."""

        self._database.reset_metrics()

    @contextmanager
    def forbid_hot_path_access(self) -> Iterator[None]:
        """Reject any repository access in the current runtime context."""

        with self._database.forbid_hot_path_access():
            yield

    @contextmanager
    def inject_failures(self) -> Iterator[None]:
        """Inject pre-SQLite failures into every repository operation."""

        with self._database.inject_failures():
            yield

    def create_principal(self, request: PrincipalCreate) -> PrincipalRecord:
        """Persist a durable principal transactionally."""

        now = self._now()
        metadata_json = canonical_json(request.metadata)
        metadata_digest = canonical_digest(request.metadata)
        with self._database.transaction("create_principal") as connection:
            try:
                connection.execute(
                    """
                    INSERT INTO principals(
                        principal_id, principal_kind, display_name, credential_hash,
                        created_at, metadata_json, metadata_digest
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(request.principal_id),
                        request.principal_kind.value,
                        request.display_name,
                        request.credential_hash,
                        datetime_to_text(now),
                        metadata_json,
                        metadata_digest,
                    ),
                )
            except sqlite3.IntegrityError as exc:
                raise ConflictError(f"Principal {request.principal_id} already exists") from exc
            row = self._required_row(
                connection,
                "SELECT * FROM principals WHERE principal_id = ?",
                (str(request.principal_id),),
                "principal",
            )
        return _principal_from_row(row)

    def get_principal(self, principal_id: UUID) -> PrincipalRecord:
        """Return one durable principal by identifier."""

        with self._database.read("get_principal") as connection:
            row = self._required_row(
                connection,
                "SELECT * FROM principals WHERE principal_id = ?",
                (str(principal_id),),
                "principal",
            )
        return _principal_from_row(row)

    def resolve_player_identity(
        self,
        identity_key: str,
        principal_request: PrincipalCreate,
    ) -> tuple[PrincipalRecord, PlayerIdentityRecord]:
        """Resolve or atomically create one normalized name identity."""

        now = self._now()
        with self._database.transaction("resolve_player_identity") as connection:
            identity_row = connection.execute(
                """
                SELECT i.identity_key, i.display_name AS identity_display_name,
                       i.created_at AS identity_created_at, p.*
                FROM player_identities AS i
                JOIN principals AS p ON p.principal_id = i.principal_id
                WHERE i.identity_key = ?
                """,
                (identity_key,),
            ).fetchone()
            if identity_row is None:
                metadata_json = canonical_json(principal_request.metadata)
                metadata_digest = canonical_digest(principal_request.metadata)
                connection.execute(
                    """
                    INSERT INTO principals(
                        principal_id, principal_kind, display_name, credential_hash,
                        created_at, last_seen_at, metadata_json, metadata_digest
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(principal_request.principal_id),
                        principal_request.principal_kind.value,
                        principal_request.display_name,
                        principal_request.credential_hash,
                        datetime_to_text(now),
                        datetime_to_text(now),
                        metadata_json,
                        metadata_digest,
                    ),
                )
                connection.execute(
                    """
                    INSERT INTO player_identities(identity_key, principal_id, display_name, created_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        identity_key,
                        str(principal_request.principal_id),
                        principal_request.display_name,
                        datetime_to_text(now),
                    ),
                )
            else:
                connection.execute(
                    "UPDATE principals SET last_seen_at = ? WHERE principal_id = ?",
                    (datetime_to_text(now), identity_row["principal_id"]),
                )
            resolved_row = self._required_row(
                connection,
                """
                SELECT i.identity_key, i.display_name AS identity_display_name,
                       i.created_at AS identity_created_at, p.*
                FROM player_identities AS i
                JOIN principals AS p ON p.principal_id = i.principal_id
                WHERE i.identity_key = ?
                """,
                (identity_key,),
                "player identity",
            )
        return _principal_from_row(resolved_row), _player_identity_from_row(resolved_row)

    def issue_principal_credential(
        self,
        request: PrincipalCredentialCreate,
    ) -> PrincipalCredentialRecord:
        """Persist one independently revocable credential for a client instance."""

        now = self._now()
        with self._database.transaction("issue_principal_credential") as connection:
            self._required_row(
                connection,
                "SELECT principal_id FROM principals WHERE principal_id = ?",
                (str(request.principal_id),),
                "principal",
            )
            connection.execute(
                """
                INSERT INTO principal_credentials(
                    credential_id, principal_id, client_instance_id, secret_hash, issued_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    str(request.credential_id),
                    str(request.principal_id),
                    request.client_instance_id,
                    request.secret_hash,
                    datetime_to_text(now),
                ),
            )
            row = self._required_row(
                connection,
                "SELECT * FROM principal_credentials WHERE credential_id = ?",
                (str(request.credential_id),),
                "principal credential",
            )
        return _principal_credential_from_row(row)

    def authenticate_principal_credential(
        self,
        principal_id: UUID,
        capability: str,
    ) -> PrincipalCredentialRecord:
        """Validate one client credential and update its activity timestamp."""

        secret_hash = hash_capability(capability, self._capability_pepper)
        now = self._now()
        with self._database.transaction("authenticate_principal_credential") as connection:
            row = self._required_row(
                connection,
                """
                SELECT * FROM principal_credentials
                WHERE principal_id = ? AND secret_hash = ? AND revoked_at IS NULL
                """,
                (str(principal_id), secret_hash),
                "principal credential",
            )
            connection.execute(
                "UPDATE principal_credentials SET last_seen_at = ? WHERE credential_id = ?",
                (datetime_to_text(now), row["credential_id"]),
            )
            refreshed = self._required_row(
                connection,
                "SELECT * FROM principal_credentials WHERE credential_id = ?",
                (row["credential_id"],),
                "principal credential",
            )
        return _principal_credential_from_row(refreshed)

    def create_profile_settings(
        self,
        request: ProfileSettingsCreate,
    ) -> ProfileSettingsRecord:
        """Create the one rules-policy row owned by a principal."""

        now = self._now()
        with self._database.transaction("create_profile_settings") as connection:
            self._required_row(
                connection,
                "SELECT principal_id FROM principals WHERE principal_id = ?",
                (str(request.owner_principal_id),),
                "principal",
            )
            try:
                connection.execute(
                    """
                    INSERT INTO profile_settings(
                        owner_principal_id,
                        permissive_multiclass_prerequisites,
                        multiclass_slot_rounding_policy,
                        allow_respec,
                        spell_preparation_policy,
                        settings_version,
                        ruleset_digest,
                        updated_at
                    ) VALUES (?, ?, ?, ?, ?, 1, ?, ?)
                    """,
                    (
                        str(request.owner_principal_id),
                        int(request.permissive_multiclass_prerequisites),
                        request.multiclass_slot_rounding_policy.value,
                        int(request.allow_respec),
                        request.spell_preparation_policy.value,
                        request.ruleset_digest,
                        datetime_to_text(now),
                    ),
                )
            except sqlite3.IntegrityError as exc:
                raise ConflictError(
                    "Profile settings already exist for this principal",
                ) from exc
            row = self._required_row(
                connection,
                "SELECT * FROM profile_settings WHERE owner_principal_id = ?",
                (str(request.owner_principal_id),),
                "profile settings",
            )
        return _profile_settings_from_row(row)

    def get_profile_settings(
        self,
        owner_principal_id: UUID,
    ) -> ProfileSettingsRecord:
        """Return the exact profile rules policy."""

        with self._database.read("get_profile_settings") as connection:
            row = self._required_row(
                connection,
                "SELECT * FROM profile_settings WHERE owner_principal_id = ?",
                (str(owner_principal_id),),
                "profile settings",
            )
        return _profile_settings_from_row(row)

    def update_profile_settings(
        self,
        request: ProfileSettingsUpdate,
    ) -> ProfileSettingsRecord:
        """Replace profile rules policy through a settings-version CAS."""

        now = self._now()
        with self._database.transaction("update_profile_settings") as connection:
            current_row = self._required_row(
                connection,
                "SELECT * FROM profile_settings WHERE owner_principal_id = ?",
                (str(request.owner_principal_id),),
                "profile settings",
            )
            if current_row["settings_version"] != request.expected_settings_version:
                raise StaleVersionError(
                    "Profile settings version changed",
                )
            cursor = connection.execute(
                """
                UPDATE profile_settings
                SET permissive_multiclass_prerequisites = ?,
                    multiclass_slot_rounding_policy = ?,
                    allow_respec = ?,
                    spell_preparation_policy = ?,
                    settings_version = settings_version + 1,
                    ruleset_digest = ?,
                    updated_at = ?
                WHERE owner_principal_id = ? AND settings_version = ?
                """,
                (
                    int(request.permissive_multiclass_prerequisites),
                    request.multiclass_slot_rounding_policy.value,
                    int(request.allow_respec),
                    request.spell_preparation_policy.value,
                    request.ruleset_digest,
                    datetime_to_text(now),
                    str(request.owner_principal_id),
                    request.expected_settings_version,
                ),
            )
            if cursor.rowcount != 1:
                raise StaleVersionError("Profile settings version changed")
            row = self._required_row(
                connection,
                "SELECT * FROM profile_settings WHERE owner_principal_id = ?",
                (str(request.owner_principal_id),),
                "profile settings",
            )
        return _profile_settings_from_row(row)

    def create_character_advancement_award(
        self,
        request: CharacterAdvancementAwardCreate,
    ) -> CharacterAdvancementAwardRecord:
        """Append an idempotent source-owned level entitlement."""

        with self._database.transaction(
            "create_character_advancement_award",
        ) as connection:
            row = self._insert_character_advancement_award(
                connection,
                request,
                created_at=self._now(),
            )
        return _character_advancement_award_from_row(row)

    def create_character_advancement_award_if_expected_level(
        self,
        request: CharacterAdvancementAwardCreate,
        *,
        expected_earned_character_level: int,
        maximum_character_level: int = 20,
    ) -> CharacterAdvancementAwardRecord:
        """Append one award behind an atomic earned-level expectation."""

        with self._database.transaction(
            "create_character_advancement_award_if_expected_level",
        ) as connection:
            existing = connection.execute(
                """
                SELECT * FROM character_advancement_awards
                WHERE character_id = ? AND source_kind = ? AND source_id = ?
                """,
                (
                    str(request.character_id),
                    request.source_kind.value,
                    request.source_id,
                ),
            ).fetchone()
            if existing is not None:
                row = self._insert_character_advancement_award(
                    connection,
                    request,
                    created_at=self._now(),
                )
                return _character_advancement_award_from_row(row)

            current_row = connection.execute(
                """
                SELECT COALESCE(SUM(level_delta), 0) AS earned_level
                FROM character_advancement_awards
                WHERE character_id = ?
                """,
                (str(request.character_id),),
            ).fetchone()
            current_level = int(current_row["earned_level"])
            if current_level != expected_earned_character_level:
                raise StaleVersionError(
                    "Character earned level changed",
                )
            if current_level + request.level_delta > maximum_character_level:
                raise ConflictError(
                    f"Character advancement cannot exceed level "
                    f"{maximum_character_level}",
                )
            row = self._insert_character_advancement_award(
                connection,
                request,
                created_at=self._now(),
            )
        return _character_advancement_award_from_row(row)

    def list_character_advancement_awards(
        self,
        character_id: UUID,
    ) -> tuple[CharacterAdvancementAwardRecord, ...]:
        """Return deterministic advancement authority for one character."""

        with self._database.read(
            "list_character_advancement_awards",
        ) as connection:
            rows = connection.execute(
                """
                SELECT * FROM character_advancement_awards
                WHERE character_id = ?
                ORDER BY created_at, award_id
                """,
                (str(character_id),),
            ).fetchall()
        return tuple(
            _character_advancement_award_from_row(row)
            for row in rows
        )

    def get_character_earned_level(self, character_id: UUID) -> int:
        """Return the authoritative sum of immutable level awards."""

        with self._database.read("get_character_earned_level") as connection:
            self._required_row(
                connection,
                "SELECT character_id FROM characters WHERE character_id = ?",
                (str(character_id),),
                "character",
            )
            row = connection.execute(
                """
                SELECT COALESCE(SUM(level_delta), 0) AS earned_level
                FROM character_advancement_awards
                WHERE character_id = ?
                """,
                (str(character_id),),
            ).fetchone()
        return int(row["earned_level"])

    def create_character_with_revisions(
        self,
        request: CharacterBootstrapCreate,
    ) -> CanonicalCharacterRecord:
        """Atomically persist one character and all revision-one authority."""

        now = self._now()
        timestamp = datetime_to_text(now)
        definition = request.definition
        holdings = request.starter_holdings
        loadout = request.starter_loadout
        definition_json = canonical_json(definition.model_dump(mode="json"))
        holdings_json = canonical_json(holdings.model_dump(mode="json"))
        loadout_json = canonical_json(loadout.model_dump(mode="json"))
        # The historical physical column remains NOT NULL, but schema-2
        # definition JSON is the sole durable character authority.
        storage_preset_identity = (
            definition.premade_id or definition.body_recipe.ref.identity_key
        )
        with self._database.transaction(
            "create_character_with_revisions",
        ) as connection:
            self._required_row(
                connection,
                "SELECT principal_id FROM principals WHERE principal_id = ?",
                (str(request.owner_principal_id),),
                "principal",
            )
            try:
                connection.execute(
                    """
                    INSERT INTO characters(
                        character_id, owner_principal_id, display_name,
                        preset_configuration_id, status, created_at, updated_at,
                        row_version, revision_state
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, 1, 'legacy_pending')
                    """,
                    (
                        str(request.character_id),
                        str(request.owner_principal_id),
                        request.display_name,
                        storage_preset_identity,
                        request.status.value,
                        timestamp,
                        timestamp,
                    ),
                )
                connection.execute(
                    """
                    INSERT INTO character_definitions(
                        character_id, definition_revision, schema_version,
                        definition_json, definition_digest, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(definition.character_id),
                        definition.definition_revision,
                        definition.schema_version,
                        definition_json,
                        definition.definition_digest,
                        timestamp,
                    ),
                )
                connection.execute(
                    """
                    INSERT INTO character_holdings_revisions(
                        character_id, holdings_revision, schema_version,
                        holdings_json, holdings_digest, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(holdings.character_id),
                        holdings.holdings_revision,
                        holdings.schema_version,
                        holdings_json,
                        holdings.holdings_digest,
                        timestamp,
                    ),
                )
                connection.execute(
                    """
                    INSERT INTO character_loadout_revisions(
                        character_id, loadout_revision, schema_version,
                        based_on_definition_revision, loadout_json,
                        loadout_digest, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(loadout.character_id),
                        loadout.loadout_revision,
                        loadout.schema_version,
                        loadout.based_on_definition_revision,
                        loadout_json,
                        loadout.loadout_digest,
                        timestamp,
                    ),
                )
                self._insert_character_advancement_award(
                    connection,
                    request.initial_advancement_award,
                    created_at=now,
                )
                connection.execute(
                    """
                    UPDATE characters
                    SET revision_state = 'canonical',
                        current_definition_revision = ?,
                        current_definition_digest = ?,
                        current_holdings_revision = ?,
                        current_holdings_digest = ?,
                        current_loadout_revision = ?,
                        current_loadout_digest = ?
                    WHERE character_id = ?
                    """,
                    (
                        definition.definition_revision,
                        definition.definition_digest,
                        holdings.holdings_revision,
                        holdings.holdings_digest,
                        loadout.loadout_revision,
                        loadout.loadout_digest,
                        str(request.character_id),
                    ),
                )
            except sqlite3.IntegrityError as exc:
                raise ConflictError(
                    "Character revision-one bootstrap failed: "
                    f"{exc}",
                ) from exc
            row = self._required_row(
                connection,
                "SELECT * FROM characters WHERE character_id = ?",
                (str(request.character_id),),
                "character",
            )
        return _canonical_character_from_row(row)

    def get_character_definition_revision(
        self,
        character_id: UUID,
        *,
        definition_revision: int,
    ) -> CharacterDefinitionRecord:
        """Return one exact immutable structural revision."""

        if definition_revision < 1:
            raise ValueError("definition_revision must be at least 1")
        with self._database.read(
            "get_character_definition_revision",
        ) as connection:
            row = self._required_row(
                connection,
                """
                SELECT * FROM character_definitions
                WHERE character_id = ? AND definition_revision = ?
                """,
                (str(character_id), definition_revision),
                "character definition revision",
            )
        return _character_definition_from_row(row)

    def list_character_definition_revisions(
        self,
        character_id: UUID,
    ) -> tuple[CharacterDefinitionRecord, ...]:
        """Return every immutable structural revision in ascending order."""

        with self._database.read(
            "list_character_definition_revisions",
        ) as connection:
            self._required_row(
                connection,
                "SELECT character_id FROM characters WHERE character_id = ?",
                (str(character_id),),
                "character",
            )
            rows = connection.execute(
                """
                SELECT * FROM character_definitions
                WHERE character_id = ?
                ORDER BY definition_revision
                """,
                (str(character_id),),
            ).fetchall()
        return tuple(_character_definition_from_row(row) for row in rows)

    def get_character_holdings_revision(
        self,
        character_id: UUID,
        *,
        holdings_revision: int,
    ) -> CharacterHoldingsRecord:
        """Return one exact immutable holdings revision."""

        if holdings_revision < 1:
            raise ValueError("holdings_revision must be at least 1")
        with self._database.read(
            "get_character_holdings_revision",
        ) as connection:
            row = self._required_row(
                connection,
                """
                SELECT * FROM character_holdings_revisions
                WHERE character_id = ? AND holdings_revision = ?
                """,
                (str(character_id), holdings_revision),
                "character holdings revision",
            )
        return _character_holdings_from_row(row)

    def list_character_holdings_revisions(
        self,
        character_id: UUID,
    ) -> tuple[CharacterHoldingsRecord, ...]:
        """Return every immutable holdings revision in ascending order."""

        with self._database.read(
            "list_character_holdings_revisions",
        ) as connection:
            self._required_row(
                connection,
                "SELECT character_id FROM characters WHERE character_id = ?",
                (str(character_id),),
                "character",
            )
            rows = connection.execute(
                """
                SELECT * FROM character_holdings_revisions
                WHERE character_id = ?
                ORDER BY holdings_revision
                """,
                (str(character_id),),
            ).fetchall()
        return tuple(_character_holdings_from_row(row) for row in rows)

    def get_character_loadout_revision(
        self,
        character_id: UUID,
        *,
        loadout_revision: int,
    ) -> CharacterLoadoutRecord:
        """Return one exact immutable prepared-feature loadout revision."""

        if loadout_revision < 1:
            raise ValueError("loadout_revision must be at least 1")
        with self._database.read(
            "get_character_loadout_revision",
        ) as connection:
            row = self._required_row(
                connection,
                """
                SELECT * FROM character_loadout_revisions
                WHERE character_id = ? AND loadout_revision = ?
                """,
                (str(character_id), loadout_revision),
                "character loadout revision",
            )
        return _character_loadout_from_row(row)

    def list_character_loadout_revisions(
        self,
        character_id: UUID,
    ) -> tuple[CharacterLoadoutRecord, ...]:
        """Return every immutable loadout revision in ascending order."""

        with self._database.read(
            "list_character_loadout_revisions",
        ) as connection:
            self._required_row(
                connection,
                "SELECT character_id FROM characters WHERE character_id = ?",
                (str(character_id),),
                "character",
            )
            rows = connection.execute(
                """
                SELECT * FROM character_loadout_revisions
                WHERE character_id = ?
                ORDER BY loadout_revision
                """,
                (str(character_id),),
            ).fetchall()
        return tuple(_character_loadout_from_row(row) for row in rows)

    def get_directory_mutation_receipt(
        self,
        owner_principal_id: UUID,
        idempotency_key: UUID,
    ) -> DirectoryMutationReceiptRecord:
        """Return one successful durable mutation receipt by caller key."""

        with self._database.read(
            "get_directory_mutation_receipt",
        ) as connection:
            row = self._required_row(
                connection,
                """
                SELECT * FROM directory_mutation_receipts
                WHERE owner_principal_id = ? AND idempotency_key = ?
                """,
                (str(owner_principal_id), str(idempotency_key)),
                "directory mutation receipt",
            )
        return _directory_mutation_receipt_from_row(row)

    def _character_snapshot_payload(
        self,
        connection: sqlite3.Connection,
        character_row: sqlite3.Row,
    ) -> dict[str, JsonValue]:
        """Build the exact successful character result inside its transaction."""

        character = _canonical_character_from_row(character_row)
        definition_row = self._required_row(
            connection,
            """
            SELECT * FROM character_definitions
            WHERE character_id = ? AND definition_revision = ?
            """,
            (
                str(character.character_id),
                character.current_definition_revision,
            ),
            "character definition revision",
        )
        holdings_row = self._required_row(
            connection,
            """
            SELECT * FROM character_holdings_revisions
            WHERE character_id = ? AND holdings_revision = ?
            """,
            (
                str(character.character_id),
                character.current_holdings_revision,
            ),
            "character holdings revision",
        )
        loadout_row = self._required_row(
            connection,
            """
            SELECT * FROM character_loadout_revisions
            WHERE character_id = ? AND loadout_revision = ?
            """,
            (
                str(character.character_id),
                character.current_loadout_revision,
            ),
            "character loadout revision",
        )
        award_rows = connection.execute(
            """
            SELECT * FROM character_advancement_awards
            WHERE character_id = ?
            ORDER BY created_at, award_id
            """,
            (str(character.character_id),),
        ).fetchall()
        awards = tuple(
            _character_advancement_award_from_row(row)
            for row in award_rows
        )
        payload = {
            "character": character.model_dump(mode="json"),
            "heads": CharacterRevisionHeads(
                definition_revision=character.current_definition_revision,
                definition_digest=character.current_definition_digest,
                holdings_revision=character.current_holdings_revision,
                holdings_digest=character.current_holdings_digest,
                loadout_revision=character.current_loadout_revision,
                loadout_digest=character.current_loadout_digest,
            ).model_dump(mode="json"),
            "definition": _character_definition_from_row(
                definition_row,
            ).model_dump(mode="json"),
            "holdings": _character_holdings_from_row(
                holdings_row,
            ).model_dump(mode="json"),
            "loadout": _character_loadout_from_row(
                loadout_row,
            ).model_dump(mode="json"),
            "advancement": {
                "character_id": str(character.character_id),
                "earned_character_level": sum(
                    award.level_delta for award in awards
                ),
                "awards": [
                    award.model_dump(mode="json") for award in awards
                ],
            },
        }
        return TypeAdapter(dict[str, JsonValue]).validate_python(payload)

    def commit_character_revisions(
        self,
        request: CharacterRevisionBundleCommit,
    ) -> CanonicalCharacterRecord:
        """Atomically append supplied revisions and CAS all three heads."""

        now = self._now()
        timestamp = datetime_to_text(now)
        with self._database.transaction(
            "commit_character_revisions",
        ) as connection:
            receipt_request = request.mutation_receipt
            if receipt_request is not None:
                receipt_row = connection.execute(
                    """
                    SELECT * FROM directory_mutation_receipts
                    WHERE owner_principal_id = ? AND idempotency_key = ?
                    """,
                    (
                        str(receipt_request.owner_principal_id),
                        str(receipt_request.idempotency_key),
                    ),
                ).fetchone()
                if receipt_row is not None:
                    existing_receipt = (
                        _directory_mutation_receipt_from_row(receipt_row)
                    )
                    if (
                        existing_receipt.operation_kind
                        != receipt_request.operation_kind
                        or existing_receipt.scope_id
                        != receipt_request.scope_id
                        or existing_receipt.request_digest
                        != receipt_request.request_digest
                    ):
                        raise ConflictError(
                            "Directory mutation idempotency key was reused "
                            "with a different request",
                        )
                    result_character = existing_receipt.result_payload.get(
                        "character",
                    )
                    return CanonicalCharacterRecord.model_validate(
                        result_character,
                    )
            if request.settlement is not None:
                existing_settlement_row = connection.execute(
                    """
                    SELECT * FROM character_settlements
                    WHERE deployment_id = ?
                    """,
                    (str(request.settlement.deployment_id),),
                ).fetchone()
                if existing_settlement_row is not None:
                    existing = _character_settlement_from_row(
                        existing_settlement_row,
                    )
                    if (
                        existing.model_dump(exclude={"settled_at"})
                        != request.settlement.model_dump()
                    ):
                        raise ConflictError(
                            "Character deployment was already settled "
                            "with different evidence",
                        )
                    current_row = self._required_row(
                        connection,
                        "SELECT * FROM characters WHERE character_id = ?",
                        (str(request.character_id),),
                        "character",
                    )
                    return _canonical_character_from_row(current_row)

            current_row = self._required_row(
                connection,
                "SELECT * FROM characters WHERE character_id = ?",
                (str(request.character_id),),
                "character",
            )
            current = _canonical_character_from_row(current_row)
            expected = request.expected_heads
            if (
                current.row_version != request.expected_row_version
                or current.current_definition_revision
                != expected.definition_revision
                or current.current_definition_digest
                != expected.definition_digest
                or current.current_holdings_revision
                != expected.holdings_revision
                or current.current_holdings_digest != expected.holdings_digest
                or current.current_loadout_revision != expected.loadout_revision
                or current.current_loadout_digest != expected.loadout_digest
            ):
                raise StaleVersionError(
                    f"Character {request.character_id} revision heads changed",
                )

            definition = request.new_definition
            holdings = request.new_holdings
            loadout = request.new_loadout
            try:
                if definition is not None:
                    connection.execute(
                        """
                        INSERT INTO character_definitions(
                            character_id, definition_revision, schema_version,
                            definition_json, definition_digest, created_at
                        ) VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (
                            str(definition.character_id),
                            definition.definition_revision,
                            definition.schema_version,
                            canonical_json(definition.model_dump(mode="json")),
                            definition.definition_digest,
                            timestamp,
                        ),
                    )
                if holdings is not None:
                    connection.execute(
                        """
                        INSERT INTO character_holdings_revisions(
                            character_id, holdings_revision, schema_version,
                            holdings_json, holdings_digest, created_at
                        ) VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (
                            str(holdings.character_id),
                            holdings.holdings_revision,
                            holdings.schema_version,
                            canonical_json(holdings.model_dump(mode="json")),
                            holdings.holdings_digest,
                            timestamp,
                        ),
                    )
                if loadout is not None:
                    connection.execute(
                        """
                        INSERT INTO character_loadout_revisions(
                            character_id, loadout_revision, schema_version,
                            based_on_definition_revision, loadout_json,
                            loadout_digest, created_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            str(loadout.character_id),
                            loadout.loadout_revision,
                            loadout.schema_version,
                            loadout.based_on_definition_revision,
                            canonical_json(loadout.model_dump(mode="json")),
                            loadout.loadout_digest,
                            timestamp,
                        ),
                    )
                if request.advancement_award is not None:
                    self._insert_character_advancement_award(
                        connection,
                        request.advancement_award,
                        created_at=now,
                    )

                resulting_definition_revision = (
                    definition.definition_revision
                    if definition is not None
                    else current.current_definition_revision
                )
                resulting_definition_digest = (
                    definition.definition_digest
                    if definition is not None
                    else current.current_definition_digest
                )
                resulting_holdings_revision = (
                    holdings.holdings_revision
                    if holdings is not None
                    else current.current_holdings_revision
                )
                resulting_holdings_digest = (
                    holdings.holdings_digest
                    if holdings is not None
                    else current.current_holdings_digest
                )
                resulting_loadout_revision = (
                    loadout.loadout_revision
                    if loadout is not None
                    else current.current_loadout_revision
                )
                resulting_loadout_digest = (
                    loadout.loadout_digest
                    if loadout is not None
                    else current.current_loadout_digest
                )
                cursor = connection.execute(
                    """
                    UPDATE characters
                    SET current_definition_revision = ?,
                        current_definition_digest = ?,
                        current_holdings_revision = ?,
                        current_holdings_digest = ?,
                        current_loadout_revision = ?,
                        current_loadout_digest = ?,
                        updated_at = ?,
                        row_version = row_version + 1
                    WHERE character_id = ?
                      AND revision_state = 'canonical'
                      AND current_definition_revision = ?
                      AND current_definition_digest = ?
                      AND current_holdings_revision = ?
                      AND current_holdings_digest = ?
                      AND current_loadout_revision = ?
                      AND current_loadout_digest = ?
                      AND row_version = ?
                    """,
                    (
                        resulting_definition_revision,
                        resulting_definition_digest,
                        resulting_holdings_revision,
                        resulting_holdings_digest,
                        resulting_loadout_revision,
                        resulting_loadout_digest,
                        timestamp,
                        str(request.character_id),
                        expected.definition_revision,
                        expected.definition_digest,
                        expected.holdings_revision,
                        expected.holdings_digest,
                        expected.loadout_revision,
                        expected.loadout_digest,
                        request.expected_row_version,
                    ),
                )
                if cursor.rowcount != 1:
                    raise StaleVersionError(
                        f"Character {request.character_id} revision heads changed",
                    )
                if request.settlement is not None:
                    game_row = self._required_row(
                        connection,
                        "SELECT lifecycle_state FROM games WHERE game_id = ?",
                        (str(request.settlement.game_id),),
                        "settlement game",
                    )
                    if (
                        GameLifecycleState(game_row["lifecycle_state"])
                        is not GameLifecycleState.ENDED
                    ):
                        raise ConflictError(
                            "Character settlement requires an ended game",
                        )
                    settlement = request.settlement
                    connection.execute(
                        """
                        INSERT INTO character_settlements(
                            settlement_id, deployment_id, game_id, character_id,
                            starting_holdings_revision,
                            starting_holdings_digest,
                            resulting_holdings_revision,
                            resulting_holdings_digest,
                            delta_digest, settled_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            str(settlement.settlement_id),
                            str(settlement.deployment_id),
                            str(settlement.game_id),
                            str(settlement.character_id),
                            settlement.starting_holdings_revision,
                            settlement.starting_holdings_digest,
                            settlement.resulting_holdings_revision,
                            settlement.resulting_holdings_digest,
                            settlement.delta_digest,
                            timestamp,
                        ),
                    )
            except sqlite3.IntegrityError as exc:
                raise ConflictError(
                    f"Character revision bundle failed: {exc}",
                ) from exc
            updated_row = self._required_row(
                connection,
                "SELECT * FROM characters WHERE character_id = ?",
                (str(request.character_id),),
                "character",
            )
            if receipt_request is not None:
                result_payload = self._character_snapshot_payload(
                    connection,
                    updated_row,
                )
                result_digest = canonical_digest(result_payload)
                try:
                    connection.execute(
                        """
                        INSERT INTO directory_mutation_receipts(
                            owner_principal_id, idempotency_key,
                            operation_kind, scope_id, request_digest,
                            result_payload_json, result_digest, created_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            str(receipt_request.owner_principal_id),
                            str(receipt_request.idempotency_key),
                            receipt_request.operation_kind,
                            str(receipt_request.scope_id),
                            receipt_request.request_digest,
                            canonical_json(result_payload),
                            result_digest,
                            timestamp,
                        ),
                    )
                except sqlite3.IntegrityError as exc:
                    raise ConflictError(
                        f"Directory mutation receipt failed: {exc}",
                    ) from exc
        return _canonical_character_from_row(updated_row)

    def append_character_holdings_revision(
        self,
        holdings: CharacterHoldingsRevision,
        *,
        expected_holdings_revision: int,
        expected_holdings_digest: str,
        expected_row_version: int,
    ) -> CanonicalCharacterRecord:
        """Append holdings through the one three-head bundle CAS."""

        if expected_holdings_revision < 1:
            raise ValueError("expected_holdings_revision must be at least 1")
        if expected_row_version < 1:
            raise ValueError("expected_row_version must be at least 1")
        if holdings.holdings_revision != expected_holdings_revision + 1:
            raise ValueError(
                "new holdings revision must increase the expected revision "
                "by exactly one",
            )
        current = self.get_character(holdings.character_id)
        canonical = CanonicalCharacterRecord.model_validate(current.model_dump())
        return self.commit_character_revisions(
            CharacterRevisionBundleCommit(
                character_id=holdings.character_id,
                expected_row_version=expected_row_version,
                expected_heads=CharacterRevisionHeads(
                    definition_revision=canonical.current_definition_revision,
                    definition_digest=canonical.current_definition_digest,
                    holdings_revision=expected_holdings_revision,
                    holdings_digest=expected_holdings_digest,
                    loadout_revision=canonical.current_loadout_revision,
                    loadout_digest=canonical.current_loadout_digest,
                ),
                new_holdings=holdings,
            ),
        )

    def get_character(self, character_id: UUID) -> CharacterRecord:
        """Return one persistent character by identifier."""

        with self._database.read("get_character") as connection:
            row = self._required_row(
                connection,
                "SELECT * FROM characters WHERE character_id = ?",
                (str(character_id),),
                "character",
            )
        return _character_from_row(row)

    def list_characters_for_principal(self, principal_id: UUID) -> tuple[CharacterRecord, ...]:
        """Return a player's characters in deterministic creation order."""

        with self._database.read("list_characters_for_principal") as connection:
            rows = connection.execute(
                """
                SELECT * FROM characters
                WHERE owner_principal_id = ?
                ORDER BY created_at, character_id
                """,
                (str(principal_id),),
            ).fetchall()
        return tuple(_character_from_row(row) for row in rows)

    def acquire_character_deployment_lease(
        self,
        request: CharacterDeploymentLeaseCreate,
    ) -> CharacterDeploymentLeaseRecord:
        """Acquire the one active live-deployment lease for a character."""

        now = self._now()
        with self._database.transaction(
            "acquire_character_deployment_lease",
        ) as connection:
            ownership_row = self._required_row(
                connection,
                """
                SELECT
                    character.status,
                    character.revision_state,
                    character.owner_principal_id,
                    membership.game_id AS membership_game_id,
                    membership.principal_id AS membership_principal_id,
                    membership.membership_state,
                    membership.may_control_entities
                FROM characters AS character
                JOIN game_memberships AS membership
                  ON membership.membership_id = ?
                WHERE character.character_id = ?
                """,
                (
                    str(request.membership_id),
                    str(request.character_id),
                ),
                "character deployment authority",
            )
            if ownership_row["revision_state"] != CharacterRevisionState.CANONICAL.value:
                raise ConflictError(
                    "Character requires canonical revisions before deployment",
                )
            if ownership_row["status"] != "active":
                raise ConflictError("Retired characters cannot be deployed")
            if ownership_row["membership_game_id"] != str(request.game_id):
                raise ConflictError(
                    "Character deployment membership belongs to another game",
                )
            if (
                ownership_row["membership_principal_id"]
                != ownership_row["owner_principal_id"]
            ):
                raise ConflictError(
                    "Character deployment membership does not belong to the "
                    "character owner",
                )
            if ownership_row["membership_state"] != MembershipState.ACTIVE.value:
                raise ConflictError(
                    "Character deployment requires an active membership",
                )
            if not bool(ownership_row["may_control_entities"]):
                raise ConflictError(
                    "Character deployment membership does not have "
                    "entity-control authority",
                )
            try:
                connection.execute(
                    """
                    INSERT INTO character_deployment_leases(
                        lease_id, character_id, game_id, membership_id,
                        acquired_at
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        str(request.lease_id),
                        str(request.character_id),
                        str(request.game_id),
                        str(request.membership_id),
                        datetime_to_text(now),
                    ),
                )
            except sqlite3.IntegrityError as exc:
                active = connection.execute(
                    """
                    SELECT lease_id FROM character_deployment_leases
                    WHERE character_id = ? AND released_at IS NULL
                    """,
                    (str(request.character_id),),
                ).fetchone()
                if active is not None:
                    raise ConflictError(
                        f"Character {request.character_id} already has an "
                        "active deployment lease",
                    ) from exc
                raise ConflictError(
                    f"Character deployment lease could not be acquired: {exc}",
                ) from exc
            row = self._required_row(
                connection,
                """
                SELECT * FROM character_deployment_leases
                WHERE lease_id = ?
                """,
                (str(request.lease_id),),
                "character deployment lease",
            )
        return _character_deployment_lease_from_row(row)

    def get_active_character_deployment_lease(
        self,
        character_id: UUID,
    ) -> CharacterDeploymentLeaseRecord | None:
        """Return the character's active lease without creating authority."""

        with self._database.read(
            "get_active_character_deployment_lease",
        ) as connection:
            self._required_row(
                connection,
                "SELECT character_id FROM characters WHERE character_id = ?",
                (str(character_id),),
                "character",
            )
            row = connection.execute(
                """
                SELECT * FROM character_deployment_leases
                WHERE character_id = ? AND released_at IS NULL
                """,
                (str(character_id),),
            ).fetchone()
        return (
            None
            if row is None
            else _character_deployment_lease_from_row(row)
        )

    def list_character_deployment_leases(
        self,
        *,
        game_id: UUID | None = None,
        active_only: bool = False,
    ) -> tuple[CharacterDeploymentLeaseRecord, ...]:
        """List durable leases for lifecycle recovery and reconciliation."""

        predicates: list[str] = []
        parameters: list[str] = []
        if game_id is not None:
            predicates.append("game_id = ?")
            parameters.append(str(game_id))
        if active_only:
            predicates.append("released_at IS NULL")
        where_clause = (
            f"WHERE {' AND '.join(predicates)}"
            if predicates
            else ""
        )
        with self._database.read(
            "list_character_deployment_leases",
        ) as connection:
            rows = connection.execute(
                f"""
                SELECT * FROM character_deployment_leases
                {where_clause}
                ORDER BY acquired_at, lease_id
                """,
                tuple(parameters),
            ).fetchall()
        return tuple(
            _character_deployment_lease_from_row(row)
            for row in rows
        )

    def release_character_deployment_lease(
        self,
        lease_id: UUID,
        *,
        release_reason: str,
    ) -> CharacterDeploymentLeaseRecord:
        """Release one active lease, accepting an exact idempotent retry."""

        if not release_reason:
            raise ValueError("release_reason cannot be empty")
        now = self._now()
        with self._database.transaction(
            "release_character_deployment_lease",
        ) as connection:
            current_row = self._required_row(
                connection,
                """
                SELECT * FROM character_deployment_leases
                WHERE lease_id = ?
                """,
                (str(lease_id),),
                "character deployment lease",
            )
            current = _character_deployment_lease_from_row(current_row)
            if current.released_at is not None:
                if current.release_reason != release_reason:
                    raise ConflictError(
                        "Character deployment lease was already released "
                        "for a different reason",
                    )
                return current
            connection.execute(
                """
                UPDATE character_deployment_leases
                SET released_at = ?, release_reason = ?
                WHERE lease_id = ? AND released_at IS NULL
                """,
                (
                    datetime_to_text(now),
                    release_reason,
                    str(lease_id),
                ),
            )
            released_row = self._required_row(
                connection,
                """
                SELECT * FROM character_deployment_leases
                WHERE lease_id = ?
                """,
                (str(lease_id),),
                "character deployment lease",
            )
        return _character_deployment_lease_from_row(released_row)

    def deploy_character_pinned(
        self,
        request: PinnedCharacterDeploymentCreate,
    ) -> PinnedCharacterDeploymentRecord:
        """Persist a deployment pinned to the leased character's exact heads."""

        now = self._now()
        with self._database.transaction(
            "deploy_character_pinned",
        ) as connection:
            lease_row = self._required_row(
                connection,
                """
                SELECT * FROM character_deployment_leases
                WHERE lease_id = ?
                """,
                (str(request.lease_id),),
                "character deployment lease",
            )
            lease = _character_deployment_lease_from_row(lease_row)
            if lease.released_at is not None:
                raise ConflictError(
                    "Pinned character deployment requires an active lease",
                )
            if (
                lease.character_id != request.character_id
                or lease.game_id != request.game_id
                or lease.membership_id != request.membership_id
            ):
                raise ConflictError(
                    "Pinned character deployment does not match its lease",
                )
            character_row = self._required_row(
                connection,
                "SELECT * FROM characters WHERE character_id = ?",
                (str(request.character_id),),
                "character",
            )
            character = _canonical_character_from_row(character_row)
            try:
                connection.execute(
                    """
                    INSERT INTO character_deployments(
                        deployment_id, game_id, membership_id, character_id,
                        entity_uuid, deployed_at, lease_id, pin_state,
                        definition_revision, definition_digest,
                        holdings_revision, holdings_digest,
                        loadout_revision, loadout_digest
                    ) VALUES (
                        ?, ?, ?, ?, ?, ?, ?, 'pinned',
                        ?, ?, ?, ?, ?, ?
                    )
                    """,
                    (
                        str(request.deployment_id),
                        str(request.game_id),
                        str(request.membership_id),
                        str(request.character_id),
                        str(request.entity_uuid),
                        datetime_to_text(now),
                        str(request.lease_id),
                        character.current_definition_revision,
                        character.current_definition_digest,
                        character.current_holdings_revision,
                        character.current_holdings_digest,
                        character.current_loadout_revision,
                        character.current_loadout_digest,
                    ),
                )
            except sqlite3.IntegrityError as exc:
                raise ConflictError(
                    f"Pinned character deployment could not be created: {exc}",
                ) from exc
            row = self._required_row(
                connection,
                """
                SELECT * FROM character_deployments
                WHERE deployment_id = ?
                """,
                (str(request.deployment_id),),
                "character deployment",
            )
        return _pinned_character_deployment_from_row(row)

    def list_character_deployments(
        self,
        character_id: UUID,
    ) -> tuple[PinnedCharacterDeploymentRecord, ...]:
        """Return only revision-pinned deployment history for one character."""

        with self._database.read("list_character_deployments") as connection:
            rows = connection.execute(
                """
                SELECT * FROM character_deployments
                WHERE character_id = ?
                ORDER BY deployed_at, deployment_id
                """,
                (str(character_id),),
            ).fetchall()
        return tuple(
            _pinned_character_deployment_from_row(row)
            for row in rows
        )

    def get_character_settlement_by_deployment(
        self,
        deployment_id: UUID,
    ) -> CharacterSettlementRecord:
        """Return the unique immutable settlement receipt for a deployment."""

        with self._database.read(
            "get_character_settlement_by_deployment",
        ) as connection:
            row = self._required_row(
                connection,
                """
                SELECT * FROM character_settlements
                WHERE deployment_id = ?
                """,
                (str(deployment_id),),
                "character settlement",
            )
        return _character_settlement_from_row(row)

    def create_worker(self, request: WorkerCreate) -> WorkerRecord:
        """Persist one isolated worker placement record."""

        now = self._now()
        with self._database.transaction("create_worker") as connection:
            try:
                connection.execute(
                    """
                    INSERT INTO workers(
                        worker_id, worker_generation, state, pid, process_group_id,
                        host_id, transport_kind, private_locator, started_at,
                        lease_expires_at, protocol_hash, engine_version,
                        failure_detail_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(request.worker_id),
                        request.worker_generation,
                        request.state.value,
                        request.pid,
                        request.process_group_id,
                        request.host_id,
                        request.transport_kind.value,
                        request.private_locator,
                        datetime_to_text(now),
                        _optional_text(request.lease_expires_at),
                        request.protocol_hash,
                        request.engine_version,
                        canonical_json({}),
                    ),
                )
            except sqlite3.IntegrityError as exc:
                raise ConflictError(f"Worker {request.worker_id} already exists") from exc
            row = self._required_row(
                connection,
                "SELECT * FROM workers WHERE worker_id = ?",
                (str(request.worker_id),),
                "worker",
            )
        return _worker_from_row(row)

    def get_worker(self, worker_id: UUID) -> WorkerRecord:
        """Return one worker placement record."""

        with self._database.read("get_worker") as connection:
            row = self._required_row(
                connection,
                "SELECT * FROM workers WHERE worker_id = ?",
                (str(worker_id),),
                "worker",
            )
        return _worker_from_row(row)

    def update_worker(
        self,
        worker_id: UUID,
        *,
        state: WorkerState,
        lease_expires_at: datetime | None = None,
        stopped_at: datetime | None = None,
        failure_code: str | None = None,
        failure_detail: JsonObject | None = None,
        heartbeat: bool = False,
    ) -> WorkerRecord:
        """Update worker lifecycle and heartbeat evidence transactionally."""

        now = self._now()
        detail = failure_detail or {}
        with self._database.transaction("update_worker") as connection:
            cursor = connection.execute(
                """
                UPDATE workers
                SET state = ?, lease_expires_at = ?, stopped_at = ?,
                    failure_code = ?, failure_detail_json = ?,
                    last_heartbeat_at = CASE WHEN ? THEN ? ELSE last_heartbeat_at END
                WHERE worker_id = ?
                """,
                (
                    state.value,
                    _optional_text(lease_expires_at),
                    _optional_text(stopped_at),
                    failure_code,
                    canonical_json(detail),
                    int(heartbeat),
                    datetime_to_text(now),
                    str(worker_id),
                ),
            )
            if cursor.rowcount != 1:
                raise NotFoundError(f"Worker {worker_id} does not exist")
            row = self._required_row(
                connection,
                "SELECT * FROM workers WHERE worker_id = ?",
                (str(worker_id),),
                "worker",
            )
        return _worker_from_row(row)

    def create_game(self, request: GameCreate) -> GameRecord:
        """Reserve one game with an exact canonical creation manifest."""

        now = self._now()
        manifest_json = canonical_json(request.creation_manifest)
        manifest_digest = canonical_digest(request.creation_manifest)
        with self._database.transaction("create_game") as connection:
            self._validate_worker_binding(
                connection,
                request.worker_id,
                request.worker_generation,
            )
            try:
                connection.execute(
                    """
                    INSERT INTO games(
                        game_id, engine_game_id, worker_id, worker_generation,
                        created_by_principal_id, lifecycle_state, visibility_policy,
                        observer_policy, execution_kind, scenario_kind, scenario_id,
                        display_name, creation_manifest_json,
                        creation_manifest_digest, seed, ruleset_version,
                        engine_version, content_digest, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(request.game_id),
                        str(request.engine_game_id) if request.engine_game_id else None,
                        str(request.worker_id) if request.worker_id else None,
                        request.worker_generation,
                        str(request.created_by_principal_id),
                        request.lifecycle_state.value,
                        request.visibility_policy.value,
                        request.observer_policy.value,
                        request.execution_kind.value,
                        request.scenario_kind,
                        request.scenario_id,
                        request.display_name,
                        manifest_json,
                        manifest_digest,
                        request.seed,
                        request.ruleset_version,
                        request.engine_version,
                        request.content_digest,
                        datetime_to_text(now),
                    ),
                )
            except sqlite3.IntegrityError as exc:
                raise ConflictError(f"Game {request.game_id} could not be created: {exc}") from exc
            row = self._required_row(
                connection,
                "SELECT * FROM games WHERE game_id = ?",
                (str(request.game_id),),
                "game",
            )
            self._append_event_in_transaction(
                connection,
                game_id=request.game_id,
                event_type="game_reserved",
                payload={"lifecycle_state": request.lifecycle_state.value},
                created_at=now,
            )
        return _game_from_row(row)

    def get_game(self, game_id: UUID) -> GameRecord:
        """Return one hosted game record."""

        with self._database.read("get_game") as connection:
            row = self._required_row(
                connection,
                "SELECT * FROM games WHERE game_id = ?",
                (str(game_id),),
                "game",
            )
        return _game_from_row(row)

    def list_games(
        self,
        *,
        lifecycle_state: GameLifecycleState | None = None,
        limit: int = 100,
    ) -> tuple[GameRecord, ...]:
        """List games newest first with an optional lifecycle filter."""

        if limit < 1 or limit > 1_000:
            raise ValueError("limit must be between 1 and 1000")
        with self._database.read("list_games") as connection:
            if lifecycle_state is None:
                rows = connection.execute(
                    "SELECT * FROM games ORDER BY created_at DESC LIMIT ?",
                    (limit,),
                ).fetchall()
            else:
                rows = connection.execute(
                    "SELECT * FROM games WHERE lifecycle_state = ? ORDER BY created_at DESC LIMIT ?",
                    (lifecycle_state.value, limit),
                ).fetchall()
        return tuple(_game_from_row(row) for row in rows)

    def transition_game(
        self,
        game_id: UUID,
        *,
        expected_row_version: int,
        lifecycle_state: GameLifecycleState,
        engine_game_id: UUID | None = None,
        worker_id: UUID | None = None,
        worker_generation: int | None = None,
        terminal_reason: str | None = None,
        winner_side_id: str | None = None,
        final_event_cursor: int | None = None,
        final_combat_log_cursor: int | None = None,
    ) -> GameRecord:
        """Compare-and-swap one game lifecycle transition."""

        now = self._now()
        with self._database.transaction("transition_game") as connection:
            return self._transition_game_in_transaction(
                connection,
                game_id,
                expected_row_version=expected_row_version,
                lifecycle_state=lifecycle_state,
                engine_game_id=engine_game_id,
                worker_id=worker_id,
                worker_generation=worker_generation,
                terminal_reason=terminal_reason,
                winner_side_id=winner_side_id,
                final_event_cursor=final_event_cursor,
                final_combat_log_cursor=final_combat_log_cursor,
                now=now,
            )

    def terminate_game_and_release_leases(
        self,
        game_id: UUID,
        *,
        expected_row_version: int,
        lifecycle_state: GameLifecycleState,
        terminal_reason: str,
    ) -> GameRecord:
        """Atomically terminate one game and release all of its active leases."""

        if lifecycle_state not in {
            GameLifecycleState.FAILED,
            GameLifecycleState.INTERRUPTED,
        }:
            raise ValueError(
                "Non-evidence termination must fail or interrupt the game",
            )
        if not terminal_reason:
            raise ValueError("terminal_reason cannot be empty")
        now = self._now()
        timestamp = datetime_to_text(now)
        with self._database.transaction(
            "terminate_game_and_release_leases",
        ) as connection:
            connection.execute(
                """
                UPDATE character_deployment_leases
                SET released_at = ?, release_reason = ?
                WHERE game_id = ? AND released_at IS NULL
                """,
                (timestamp, terminal_reason, str(game_id)),
            )
            return self._transition_game_in_transaction(
                connection,
                game_id,
                expected_row_version=expected_row_version,
                lifecycle_state=lifecycle_state,
                terminal_reason=terminal_reason,
                now=now,
            )

    def _transition_game_in_transaction(
        self,
        connection: sqlite3.Connection,
        game_id: UUID,
        *,
        expected_row_version: int,
        lifecycle_state: GameLifecycleState,
        engine_game_id: UUID | None = None,
        worker_id: UUID | None = None,
        worker_generation: int | None = None,
        terminal_reason: str | None = None,
        winner_side_id: str | None = None,
        final_event_cursor: int | None = None,
        final_combat_log_cursor: int | None = None,
        now: datetime,
    ) -> GameRecord:
        """Apply one game lifecycle CAS inside an existing transaction."""

        current_row = self._required_row(
            connection,
            "SELECT * FROM games WHERE game_id = ?",
            (str(game_id),),
            "game",
        )
        current = _game_from_row(current_row)
        if current.row_version != expected_row_version:
            raise StaleVersionError(
                f"Game {game_id} row version is {current.row_version}, "
                f"expected {expected_row_version}",
            )
        resolved_worker_id = (
            worker_id if worker_id is not None else current.worker_id
        )
        resolved_generation = (
            worker_generation
            if worker_generation is not None
            else current.worker_generation
        )
        self._validate_worker_binding(
            connection,
            resolved_worker_id,
            resolved_generation,
        )
        started_at = current.started_at
        ended_at = current.ended_at
        archived_at = current.archived_at
        if lifecycle_state is GameLifecycleState.ACTIVE and started_at is None:
            started_at = now
        if lifecycle_state in {
            GameLifecycleState.ENDED,
            GameLifecycleState.FAILED,
            GameLifecycleState.INTERRUPTED,
        } and ended_at is None:
            ended_at = now
        if (
            lifecycle_state is GameLifecycleState.ARCHIVED
            and archived_at is None
        ):
            archived_at = now
        cursor = connection.execute(
            """
            UPDATE games
            SET lifecycle_state = ?, engine_game_id = ?, worker_id = ?,
                worker_generation = ?, started_at = ?, ended_at = ?,
                archived_at = ?, terminal_reason = ?, winner_side_id = ?,
                final_event_cursor = ?, final_combat_log_cursor = ?,
                row_version = row_version + 1
            WHERE game_id = ? AND row_version = ?
            """,
            (
                lifecycle_state.value,
                (
                    str(engine_game_id or current.engine_game_id)
                    if (engine_game_id or current.engine_game_id)
                    else None
                ),
                str(resolved_worker_id) if resolved_worker_id else None,
                resolved_generation,
                _optional_text(started_at),
                _optional_text(ended_at),
                _optional_text(archived_at),
                (
                    terminal_reason
                    if terminal_reason is not None
                    else current.terminal_reason
                ),
                (
                    winner_side_id
                    if winner_side_id is not None
                    else current.winner_side_id
                ),
                (
                    final_event_cursor
                    if final_event_cursor is not None
                    else current.final_event_cursor
                ),
                (
                    final_combat_log_cursor
                    if final_combat_log_cursor is not None
                    else current.final_combat_log_cursor
                ),
                str(game_id),
                expected_row_version,
            ),
        )
        if cursor.rowcount != 1:
            raise StaleVersionError(
                f"Game {game_id} changed during lifecycle transition",
            )
        self._append_event_in_transaction(
            connection,
            game_id=game_id,
            event_type="game_lifecycle_changed",
            payload={
                "from": current.lifecycle_state.value,
                "to": lifecycle_state.value,
                "row_version": expected_row_version + 1,
            },
            created_at=now,
        )
        row = self._required_row(
            connection,
            "SELECT * FROM games WHERE game_id = ?",
            (str(game_id),),
            "game",
        )
        return _game_from_row(row)

    def create_membership(self, request: MembershipCreate) -> MembershipRecord:
        """Create one membership and its explicit authority atomically."""

        now = self._now()
        caps = request.capabilities
        with self._database.transaction("create_membership") as connection:
            if request.subjective_source_membership_id is not None:
                source_row = self._required_row(
                    connection,
                    "SELECT game_id FROM game_memberships WHERE membership_id = ?",
                    (str(request.subjective_source_membership_id),),
                    "subjective source membership",
                )
                if source_row["game_id"] != str(request.game_id):
                    raise ConflictError("Subjective source membership belongs to another game")
            try:
                connection.execute(
                    """
                    INSERT INTO game_memberships(
                        membership_id, game_id, principal_id, role, side_id,
                        controller_kind, membership_state, may_connect,
                        may_observe_public_state, may_observe_subjective_state,
                        may_control_entities, may_view_agent_telemetry,
                        may_manage_members, may_manage_game,
                        may_view_objective_replay, subjective_source_membership_id,
                        authority_epoch, joined_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(request.membership_id),
                        str(request.game_id),
                        str(request.principal_id),
                        request.role.value,
                        request.side_id,
                        request.controller_kind,
                        request.membership_state.value,
                        int(caps.may_connect),
                        int(caps.may_observe_public_state),
                        int(caps.may_observe_subjective_state),
                        int(caps.may_control_entities),
                        int(caps.may_view_agent_telemetry),
                        int(caps.may_manage_members),
                        int(caps.may_manage_game),
                        int(caps.may_view_objective_replay),
                        str(request.subjective_source_membership_id)
                        if request.subjective_source_membership_id
                        else None,
                        request.authority_epoch,
                        datetime_to_text(now),
                    ),
                )
            except sqlite3.IntegrityError as exc:
                raise ConflictError(f"Membership {request.membership_id} could not be created: {exc}") from exc
            self._append_event_in_transaction(
                connection,
                game_id=request.game_id,
                event_type="membership_created",
                payload={
                    "membership_id": str(request.membership_id),
                    "principal_id": str(request.principal_id),
                    "role": request.role.value,
                    "authority_epoch": request.authority_epoch,
                },
                created_at=now,
            )
            row = self._required_row(
                connection,
                "SELECT * FROM game_memberships WHERE membership_id = ?",
                (str(request.membership_id),),
                "membership",
            )
        return _membership_from_row(row)

    def get_membership(self, membership_id: UUID) -> MembershipRecord:
        """Return one durable game membership."""

        with self._database.read("get_membership") as connection:
            row = self._required_row(
                connection,
                "SELECT * FROM game_memberships WHERE membership_id = ?",
                (str(membership_id),),
                "membership",
            )
        return _membership_from_row(row)

    def list_memberships(self, game_id: UUID) -> tuple[MembershipRecord, ...]:
        """List all membership history for a game."""

        with self._database.read("list_memberships") as connection:
            rows = connection.execute(
                "SELECT * FROM game_memberships WHERE game_id = ? ORDER BY joined_at",
                (str(game_id),),
            ).fetchall()
        return tuple(_membership_from_row(row) for row in rows)

    def list_memberships_for_principal(
        self,
        principal_id: UUID,
    ) -> tuple[MembershipRecord, ...]:
        """List all game memberships owned by one durable principal."""

        with self._database.read("list_memberships_for_principal") as connection:
            rows = connection.execute(
                """
                SELECT * FROM game_memberships
                WHERE principal_id = ?
                ORDER BY joined_at, membership_id
                """,
                (str(principal_id),),
            ).fetchall()
        return tuple(_membership_from_row(row) for row in rows)

    def update_membership_authority(
        self,
        membership_id: UUID,
        *,
        expected_authority_epoch: int,
        membership_state: MembershipState,
        capabilities: MembershipCapabilities,
    ) -> MembershipRecord:
        """Compare-and-swap membership authority and increment its epoch."""

        now = self._now()
        with self._database.transaction("update_membership_authority") as connection:
            existing_row = self._required_row(
                connection,
                "SELECT * FROM game_memberships WHERE membership_id = ?",
                (str(membership_id),),
                "membership",
            )
            existing = _membership_from_row(existing_row)
            if existing.authority_epoch != expected_authority_epoch:
                raise StaleVersionError(
                    f"Membership {membership_id} authority epoch is {existing.authority_epoch}, "
                    f"expected {expected_authority_epoch}"
                )
            disconnected_at = now if membership_state is MembershipState.DISCONNECTED else None
            revoked_at = now if membership_state is MembershipState.REVOKED else None
            left_at = now if membership_state is MembershipState.LEFT else None
            cursor = connection.execute(
                """
                UPDATE game_memberships
                SET membership_state = ?, may_connect = ?,
                    may_observe_public_state = ?, may_observe_subjective_state = ?,
                    may_control_entities = ?, may_view_agent_telemetry = ?,
                    may_manage_members = ?, may_manage_game = ?,
                    may_view_objective_replay = ?, authority_epoch = authority_epoch + 1,
                    disconnected_at = ?, revoked_at = ?, left_at = ?
                WHERE membership_id = ? AND authority_epoch = ?
                """,
                (
                    membership_state.value,
                    int(capabilities.may_connect),
                    int(capabilities.may_observe_public_state),
                    int(capabilities.may_observe_subjective_state),
                    int(capabilities.may_control_entities),
                    int(capabilities.may_view_agent_telemetry),
                    int(capabilities.may_manage_members),
                    int(capabilities.may_manage_game),
                    int(capabilities.may_view_objective_replay),
                    _optional_text(disconnected_at),
                    _optional_text(revoked_at),
                    _optional_text(left_at),
                    str(membership_id),
                    expected_authority_epoch,
                ),
            )
            if cursor.rowcount != 1:
                raise StaleVersionError(f"Membership {membership_id} changed during update")
            self._append_event_in_transaction(
                connection,
                game_id=existing.game_id,
                event_type="membership_authority_changed",
                payload={
                    "membership_id": str(membership_id),
                    "membership_state": membership_state.value,
                    "authority_epoch": expected_authority_epoch + 1,
                },
                created_at=now,
            )
            row = self._required_row(
                connection,
                "SELECT * FROM game_memberships WHERE membership_id = ?",
                (str(membership_id),),
                "membership",
            )
        return _membership_from_row(row)

    def assign_entity(self, request: EntityAssignmentCreate) -> EntityAssignmentRecord:
        """Assign one entity while enforcing game and authority consistency."""

        now = self._now()
        with self._database.transaction("assign_entity") as connection:
            membership_row = self._required_row(
                connection,
                "SELECT game_id, authority_epoch, may_control_entities FROM game_memberships WHERE membership_id = ?",
                (str(request.membership_id),),
                "membership",
            )
            if membership_row["game_id"] != str(request.game_id):
                raise ConflictError("Entity assignment and membership belong to different games")
            if not bool(membership_row["may_control_entities"]):
                raise ConflictError("Membership does not have entity-control authority")
            if membership_row["authority_epoch"] != request.authority_epoch:
                raise StaleVersionError("Entity assignment uses a stale authority epoch")
            try:
                connection.execute(
                    """
                    INSERT INTO entity_assignments(
                        assignment_id, game_id, membership_id, entity_uuid,
                        entity_name, faction, side_id, controller_kind,
                        assigned_at, authority_epoch
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(request.assignment_id),
                        str(request.game_id),
                        str(request.membership_id),
                        str(request.entity_uuid),
                        request.entity_name,
                        request.faction,
                        request.side_id,
                        request.controller_kind,
                        datetime_to_text(now),
                        request.authority_epoch,
                    ),
                )
            except sqlite3.IntegrityError as exc:
                raise ConflictError(f"Entity {request.entity_uuid} already has active authority") from exc
            self._append_event_in_transaction(
                connection,
                game_id=request.game_id,
                event_type="entity_assigned",
                payload={
                    "assignment_id": str(request.assignment_id),
                    "membership_id": str(request.membership_id),
                    "entity_uuid": str(request.entity_uuid),
                    "authority_epoch": request.authority_epoch,
                },
                created_at=now,
            )
            row = self._required_row(
                connection,
                "SELECT * FROM entity_assignments WHERE assignment_id = ?",
                (str(request.assignment_id),),
                "entity assignment",
            )
        return _assignment_from_row(row)

    def release_entity(self, assignment_id: UUID) -> EntityAssignmentRecord:
        """Release one active entity assignment while preserving history."""

        now = self._now()
        with self._database.transaction("release_entity") as connection:
            existing_row = self._required_row(
                connection,
                "SELECT * FROM entity_assignments WHERE assignment_id = ?",
                (str(assignment_id),),
                "entity assignment",
            )
            existing = _assignment_from_row(existing_row)
            if existing.released_at is None:
                connection.execute(
                    "UPDATE entity_assignments SET released_at = ? WHERE assignment_id = ?",
                    (datetime_to_text(now), str(assignment_id)),
                )
                self._append_event_in_transaction(
                    connection,
                    game_id=existing.game_id,
                    event_type="entity_released",
                    payload={
                        "assignment_id": str(assignment_id),
                        "entity_uuid": str(existing.entity_uuid),
                    },
                    created_at=now,
                )
            row = self._required_row(
                connection,
                "SELECT * FROM entity_assignments WHERE assignment_id = ?",
                (str(assignment_id),),
                "entity assignment",
            )
        return _assignment_from_row(row)

    def list_entity_assignments(
        self,
        game_id: UUID,
        *,
        active_only: bool = True,
    ) -> tuple[EntityAssignmentRecord, ...]:
        """List current or historical entity assignments for a game."""

        with self._database.read("list_entity_assignments") as connection:
            if active_only:
                rows = connection.execute(
                    "SELECT * FROM entity_assignments WHERE game_id = ? AND released_at IS NULL ORDER BY assigned_at",
                    (str(game_id),),
                ).fetchall()
            else:
                rows = connection.execute(
                    "SELECT * FROM entity_assignments WHERE game_id = ? ORDER BY assigned_at",
                    (str(game_id),),
                ).fetchall()
        return tuple(_assignment_from_row(row) for row in rows)

    def issue_access_grant(self, request: AccessGrantCreate) -> IssuedAccessGrant:
        """Issue a high-entropy capability and persist only its HMAC digest."""

        now = self._now()
        capability = secrets.token_urlsafe(32)
        secret_hash = hash_capability(capability, self._capability_pepper)
        scope_json = canonical_json(request.scope)
        scope_digest = canonical_digest(request.scope)
        with self._database.transaction("issue_access_grant") as connection:
            self._validate_grant_scope(connection, request)
            try:
                connection.execute(
                    """
                    INSERT INTO access_grants(
                        grant_id, game_id, membership_id, issued_to_principal_id,
                        grant_kind, secret_hash, scope_json, scope_digest,
                        issued_at, expires_at, max_uses, issued_by_principal_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(request.grant_id),
                        str(request.game_id),
                        str(request.membership_id) if request.membership_id else None,
                        str(request.issued_to_principal_id) if request.issued_to_principal_id else None,
                        request.grant_kind.value,
                        secret_hash,
                        scope_json,
                        scope_digest,
                        datetime_to_text(now),
                        _optional_text(request.expires_at),
                        request.max_uses,
                        str(request.issued_by_principal_id),
                    ),
                )
            except sqlite3.IntegrityError as exc:
                raise ConflictError(f"Access grant {request.grant_id} could not be issued: {exc}") from exc
            row = self._required_row(
                connection,
                "SELECT * FROM access_grants WHERE grant_id = ?",
                (str(request.grant_id),),
                "access grant",
            )
            self._append_event_in_transaction(
                connection,
                game_id=request.game_id,
                event_type="access_grant_issued",
                payload={
                    "grant_id": str(request.grant_id),
                    "grant_kind": request.grant_kind.value,
                    "scope_digest": scope_digest,
                },
                created_at=now,
            )
        return IssuedAccessGrant(grant=_grant_from_row(row), capability=capability)

    def verify_access_grant(
        self,
        grant_id: UUID,
        capability: str,
        *,
        consume: bool = False,
    ) -> AccessGrantRecord:
        """Validate a capability and optionally consume one allowed use."""

        now = self._now()
        with self._database.transaction("verify_access_grant") as connection:
            row = self._required_row(
                connection,
                "SELECT * FROM access_grants WHERE grant_id = ?",
                (str(grant_id),),
                "access grant",
            )
            grant = _grant_from_row(row)
            supplied_hash = hash_capability(capability, self._capability_pepper)
            if not hmac.compare_digest(grant.secret_hash, supplied_hash):
                raise CapabilityError("Capability secret is invalid")
            if grant.revoked_at is not None:
                raise CapabilityError("Capability has been revoked")
            if grant.expires_at is not None and grant.expires_at <= now:
                raise CapabilityError("Capability has expired")
            if grant.max_uses is not None and grant.uses >= grant.max_uses:
                raise CapabilityError("Capability has exhausted its allowed uses")
            if consume:
                connection.execute(
                    "UPDATE access_grants SET uses = uses + 1 WHERE grant_id = ?",
                    (str(grant_id),),
                )
                row = self._required_row(
                    connection,
                    "SELECT * FROM access_grants WHERE grant_id = ?",
                    (str(grant_id),),
                    "access grant",
                )
        return _grant_from_row(row)

    def revoke_access_grant(self, grant_id: UUID) -> AccessGrantRecord:
        """Revoke one capability idempotently."""

        now = self._now()
        with self._database.transaction("revoke_access_grant") as connection:
            row = self._required_row(
                connection,
                "SELECT * FROM access_grants WHERE grant_id = ?",
                (str(grant_id),),
                "access grant",
            )
            grant = _grant_from_row(row)
            if grant.revoked_at is None:
                connection.execute(
                    "UPDATE access_grants SET revoked_at = ? WHERE grant_id = ?",
                    (datetime_to_text(now), str(grant_id)),
                )
                self._append_event_in_transaction(
                    connection,
                    game_id=grant.game_id,
                    event_type="access_grant_revoked",
                    payload={"grant_id": str(grant_id)},
                    created_at=now,
                )
                row = self._required_row(
                    connection,
                    "SELECT * FROM access_grants WHERE grant_id = ?",
                    (str(grant_id),),
                    "access grant",
                )
        return _grant_from_row(row)

    def open_attachment(self, request: AttachmentCreate) -> IssuedAttachment:
        """Open one runtime attachment and persist only its token digest."""

        now = self._now()
        runtime_token = secrets.token_urlsafe(32)
        runtime_token_hash = hash_capability(runtime_token, self._capability_pepper)
        with self._database.transaction("open_attachment") as connection:
            membership_row = self._required_row(
                connection,
                "SELECT * FROM game_memberships WHERE membership_id = ?",
                (str(request.membership_id),),
                "membership",
            )
            membership = _membership_from_row(membership_row)
            if membership.game_id != request.game_id:
                raise ConflictError("Attachment membership belongs to another game")
            if membership.membership_state not in {
                MembershipState.ACTIVE,
                MembershipState.DISCONNECTED,
            }:
                raise ConflictError("Attachment membership is not active")
            if not membership.capabilities.may_connect:
                raise ConflictError("Membership may not connect")
            if membership.authority_epoch != request.authority_epoch:
                raise StaleVersionError("Attachment uses a stale authority epoch")
            worker_row = self._required_row(
                connection,
                "SELECT worker_generation FROM workers WHERE worker_id = ?",
                (str(request.worker_id),),
                "worker",
            )
            if worker_row["worker_generation"] != request.worker_generation:
                raise StaleVersionError("Attachment targets a stale worker generation")
            game_row = self._required_row(
                connection,
                "SELECT worker_id, worker_generation FROM games WHERE game_id = ?",
                (str(request.game_id),),
                "game",
            )
            if game_row["worker_id"] != str(request.worker_id) or game_row["worker_generation"] != request.worker_generation:
                raise ConflictError("Attachment worker is not the game's current placement")
            try:
                connection.execute(
                    """
                    INSERT INTO attachments(
                        attachment_id, runtime_session_id, game_id, membership_id, worker_id,
                        worker_generation, client_kind, client_instance_id,
                        state, runtime_token_hash, connected_at, expires_at,
                        authority_epoch
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(request.attachment_id),
                        str(request.runtime_session_id),
                        str(request.game_id),
                        str(request.membership_id),
                        str(request.worker_id),
                        request.worker_generation,
                        request.client_kind.value,
                        request.client_instance_id,
                        AttachmentState.CONNECTED.value,
                        runtime_token_hash,
                        datetime_to_text(now),
                        _optional_text(request.expires_at),
                        request.authority_epoch,
                    ),
                )
            except sqlite3.IntegrityError as exc:
                raise ConflictError(f"Attachment {request.attachment_id} could not be opened: {exc}") from exc
            self._append_event_in_transaction(
                connection,
                game_id=request.game_id,
                event_type="attachment_opened",
                payload={
                    "attachment_id": str(request.attachment_id),
                    "membership_id": str(request.membership_id),
                    "client_kind": request.client_kind.value,
                },
                created_at=now,
            )
            row = self._required_row(
                connection,
                "SELECT * FROM attachments WHERE attachment_id = ?",
                (str(request.attachment_id),),
                "attachment",
            )
        return IssuedAttachment(
            attachment=_attachment_from_row(row),
            runtime_token=runtime_token,
        )

    def get_attachment(self, attachment_id: UUID) -> AttachmentRecord:
        """Return one attachment-history record."""

        with self._database.read("get_attachment") as connection:
            row = self._required_row(
                connection,
                "SELECT * FROM attachments WHERE attachment_id = ?",
                (str(attachment_id),),
                "attachment",
            )
        return _attachment_from_row(row)

    def get_latest_attachment_for_membership(
        self,
        membership_id: UUID,
    ) -> AttachmentRecord:
        """Return the newest attachment used to locate a reconnect session.

        The returned ``runtime_session_id`` is an identifier for worker-side
        rebinding. It grants no authority without a freshly validated cold
        attachment and newly issued runtime token.
        """

        with self._database.read("get_latest_attachment_for_membership") as connection:
            row = self._required_row(
                connection,
                """
                SELECT * FROM attachments
                WHERE membership_id = ?
                ORDER BY connected_at DESC, rowid DESC
                LIMIT 1
                """,
                (str(membership_id),),
                "membership attachment",
            )
        return _attachment_from_row(row)

    def list_attachments_for_membership(
        self,
        membership_id: UUID,
        *,
        connected_only: bool = False,
    ) -> tuple[AttachmentRecord, ...]:
        """List concrete client attachments for one membership."""

        with self._database.read("list_attachments_for_membership") as connection:
            if connected_only:
                rows = connection.execute(
                    """
                    SELECT * FROM attachments
                    WHERE membership_id = ? AND state = ?
                    ORDER BY connected_at, attachment_id
                    """,
                    (str(membership_id), AttachmentState.CONNECTED.value),
                ).fetchall()
            else:
                rows = connection.execute(
                    """
                    SELECT * FROM attachments
                    WHERE membership_id = ?
                    ORDER BY connected_at, attachment_id
                    """,
                    (str(membership_id),),
                ).fetchall()
        return tuple(_attachment_from_row(row) for row in rows)

    def close_attachment(
        self,
        attachment_id: UUID,
        *,
        state: AttachmentState = AttachmentState.DISCONNECTED,
        reason: str,
        last_event_cursor: int | None = None,
        last_combat_log_cursor: int | None = None,
    ) -> AttachmentRecord:
        """Close one attachment and retain its final acknowledged cursors."""

        if state is AttachmentState.CONNECTED:
            raise ValueError("close_attachment requires a terminal attachment state")
        now = self._now()
        with self._database.transaction("close_attachment") as connection:
            existing_row = self._required_row(
                connection,
                "SELECT * FROM attachments WHERE attachment_id = ?",
                (str(attachment_id),),
                "attachment",
            )
            existing = _attachment_from_row(existing_row)
            connection.execute(
                """
                UPDATE attachments
                SET state = ?, disconnected_at = ?, disconnect_reason = ?,
                    last_event_cursor = ?, last_combat_log_cursor = ?
                WHERE attachment_id = ?
                """,
                (
                    state.value,
                    datetime_to_text(now),
                    reason,
                    last_event_cursor,
                    last_combat_log_cursor,
                    str(attachment_id),
                ),
            )
            self._append_event_in_transaction(
                connection,
                game_id=existing.game_id,
                event_type="attachment_closed",
                payload={
                    "attachment_id": str(attachment_id),
                    "state": state.value,
                    "reason": reason,
                },
                created_at=now,
            )
            row = self._required_row(
                connection,
                "SELECT * FROM attachments WHERE attachment_id = ?",
                (str(attachment_id),),
                "attachment",
            )
        return _attachment_from_row(row)

    def append_directory_event(
        self,
        *,
        event_type: str,
        payload: JsonObject,
        game_id: UUID | None = None,
    ) -> DirectoryEventRecord:
        """Append one canonical lifecycle event and return its cursor."""

        if not event_type:
            raise ValueError("event_type cannot be empty")
        now = self._now()
        with self._database.transaction("append_directory_event") as connection:
            return self._append_event_in_transaction(
                connection,
                game_id=game_id,
                event_type=event_type,
                payload=payload,
                created_at=now,
            )

    def list_directory_events(
        self,
        *,
        since_cursor: int = 0,
        limit: int = 100,
        game_id: UUID | None = None,
    ) -> tuple[DirectoryEventRecord, ...]:
        """Replay ordered lifecycle events after a cursor."""

        if since_cursor < 0:
            raise ValueError("since_cursor cannot be negative")
        if limit < 1 or limit > 1_000:
            raise ValueError("limit must be between 1 and 1000")
        with self._database.read("list_directory_events") as connection:
            if game_id is None:
                rows = connection.execute(
                    "SELECT * FROM directory_events WHERE cursor > ? ORDER BY cursor LIMIT ?",
                    (since_cursor, limit),
                ).fetchall()
            else:
                rows = connection.execute(
                    "SELECT * FROM directory_events WHERE game_id = ? AND cursor > ? ORDER BY cursor LIMIT ?",
                    (str(game_id), since_cursor, limit),
                ).fetchall()
        return tuple(_event_from_row(row) for row in rows)

    def publish_artifact(self, request: ArtifactCreate) -> ArtifactRecord:
        """Publish immutable artifact metadata idempotently by content identity."""

        with self._database.transaction("publish_artifact") as connection:
            return self._publish_artifact_in_transaction(
                connection,
                request,
                created_at=self._now(),
            )

    def stage_local_terminal_commit(
        self,
        game_id: UUID,
        *,
        lease_id: UUID | None,
        payload: JsonObject,
    ) -> str:
        """Durably stage all inputs needed to finish one local terminal game."""

        payload_json = canonical_json(payload)
        payload_digest = canonical_digest(payload)
        now = self._now()
        with self._database.transaction(
            "stage_local_terminal_commit",
        ) as connection:
            existing = connection.execute(
                """
                SELECT * FROM local_terminal_commit_intents
                WHERE game_id = ?
                """,
                (str(game_id),),
            ).fetchone()
            if existing is not None:
                if (
                    existing["lease_id"]
                    != (str(lease_id) if lease_id is not None else None)
                    or existing["payload_digest"] != payload_digest
                    or existing["payload_json"] != payload_json
                ):
                    raise ImmutableRecordError(
                        "Local terminal commit was already staged with "
                        "different evidence",
                    )
                return payload_digest
            game_row = self._required_row(
                connection,
                "SELECT lifecycle_state FROM games WHERE game_id = ?",
                (str(game_id),),
                "game",
            )
            if (
                GameLifecycleState(game_row["lifecycle_state"])
                is not GameLifecycleState.ACTIVE
            ):
                raise ConflictError(
                    "Local terminal commit can only be staged for an active "
                    "game",
                )
            connection.execute(
                """
                INSERT INTO local_terminal_commit_intents(
                    game_id, lease_id, payload_json, payload_digest, staged_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    str(game_id),
                    str(lease_id) if lease_id is not None else None,
                    payload_json,
                    payload_digest,
                    datetime_to_text(now),
                ),
            )
        return payload_digest

    def stage_worker_terminal_ready_manifest(
        self,
        request: WorkerTerminalReadyManifestCreate,
    ) -> WorkerTerminalReadyManifestRecord:
        """Stage one generation-fenced hosted terminal manifest idempotently."""

        objective_json = canonical_json(
            request.objective_artifact.model_dump(mode="json"),
        )
        subjective_json = canonical_json(
            request.subjective_artifact.model_dump(mode="json"),
        )
        summary_json = canonical_json(request.summary_evidence)
        settlement_json = (
            canonical_json(request.settlement_evidence)
            if request.settlement_evidence is not None
            else None
        )
        staged_at = self._now()
        with self._database.transaction(
            "stage_worker_terminal_ready_manifest",
        ) as connection:
            game = self._required_row(
                connection,
                "SELECT * FROM games WHERE game_id = ?",
                (str(request.game_id),),
                "game",
            )
            if (
                game["worker_id"] != str(request.worker_id)
                or game["worker_generation"] != request.worker_generation
            ):
                raise StaleVersionError(
                    "Worker terminal ready manifest does not match the "
                    "game's worker generation",
                )
            if (
                GameLifecycleState(game["lifecycle_state"])
                not in {
                    GameLifecycleState.ACTIVE,
                    GameLifecycleState.ENDED,
                }
            ):
                raise ConflictError(
                    "Worker terminal ready manifest requires an active or "
                    "already-ended game",
                )
            existing = connection.execute(
                """
                SELECT * FROM worker_terminal_ready_manifests
                WHERE game_id = ?
                """,
                (str(request.game_id),),
            ).fetchone()
            if existing is not None:
                record = _worker_terminal_ready_manifest_from_row(existing)
                if (
                    record.model_dump(exclude={"staged_at", "adopted_at"})
                    != request.model_dump()
                ):
                    raise ImmutableRecordError(
                        "Worker terminal ready manifest was already staged "
                        "with different evidence",
                    )
                return record
            try:
                connection.execute(
                    """
                    INSERT INTO worker_terminal_ready_manifests(
                        game_id, worker_id, worker_generation,
                        objective_artifact_json,
                        subjective_artifact_json,
                        summary_evidence_json,
                        settlement_evidence_json,
                        manifest_digest, ready_at, staged_at, adopted_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)
                    """,
                    (
                        str(request.game_id),
                        str(request.worker_id),
                        request.worker_generation,
                        objective_json,
                        subjective_json,
                        summary_json,
                        settlement_json,
                        request.manifest_digest,
                        datetime_to_text(request.ready_at),
                        datetime_to_text(staged_at),
                    ),
                )
            except sqlite3.IntegrityError as exc:
                raise ConflictError(
                    "Worker terminal ready manifest could not be staged: "
                    f"{exc}",
                ) from exc
            row = self._required_row(
                connection,
                """
                SELECT * FROM worker_terminal_ready_manifests
                WHERE game_id = ?
                """,
                (str(request.game_id),),
                "worker terminal ready manifest",
            )
        return _worker_terminal_ready_manifest_from_row(row)

    def get_worker_terminal_ready_manifest(
        self,
        game_id: UUID,
    ) -> WorkerTerminalReadyManifestRecord:
        """Return one staged hosted terminal ready manifest."""

        with self._database.read(
            "get_worker_terminal_ready_manifest",
        ) as connection:
            row = self._required_row(
                connection,
                """
                SELECT * FROM worker_terminal_ready_manifests
                WHERE game_id = ?
                """,
                (str(game_id),),
                "worker terminal ready manifest",
            )
        return _worker_terminal_ready_manifest_from_row(row)

    def list_pending_worker_terminal_ready_manifests(
        self,
    ) -> tuple[WorkerTerminalReadyManifestRecord, ...]:
        """List generation-fenced terminal manifests awaiting adoption."""

        with self._database.read(
            "list_pending_worker_terminal_ready_manifests",
        ) as connection:
            rows = connection.execute(
                """
                SELECT * FROM worker_terminal_ready_manifests
                WHERE adopted_at IS NULL
                ORDER BY ready_at, game_id
                """,
            ).fetchall()
        return tuple(
            _worker_terminal_ready_manifest_from_row(row) for row in rows
        )

    def list_pending_local_terminal_commits(
        self,
    ) -> tuple[tuple[UUID, UUID | None, JsonObject, str], ...]:
        """Return staged local terminal inputs that still need publication."""

        with self._database.read(
            "list_pending_local_terminal_commits",
        ) as connection:
            rows = connection.execute(
                """
                SELECT game_id, lease_id, payload_json, payload_digest
                FROM local_terminal_commit_intents
                WHERE committed_at IS NULL
                ORDER BY staged_at, game_id
                """,
            ).fetchall()
        return tuple(
            (
                UUID(row["game_id"]),
                UUID(row["lease_id"]) if row["lease_id"] is not None else None,
                _load_canonical_json_object(
                    row["payload_json"],
                    "local terminal commit",
                ),
                row["payload_digest"],
            )
            for row in rows
        )

    def get_pending_local_terminal_commit(
        self,
        game_id: UUID,
    ) -> tuple[UUID | None, JsonObject, str] | None:
        """Return one staged local terminal payload when not yet committed."""

        with self._database.read(
            "get_pending_local_terminal_commit",
        ) as connection:
            row = connection.execute(
                """
                SELECT lease_id, payload_json, payload_digest
                FROM local_terminal_commit_intents
                WHERE game_id = ? AND committed_at IS NULL
                """,
                (str(game_id),),
            ).fetchone()
        if row is None:
            return None
        return (
            UUID(row["lease_id"]) if row["lease_id"] is not None else None,
            _load_canonical_json_object(
                row["payload_json"],
                "local terminal commit",
            ),
            row["payload_digest"],
        )

    def _publish_artifact_in_transaction(
        self,
        connection: sqlite3.Connection,
        request: ArtifactCreate,
        *,
        created_at: datetime,
    ) -> ArtifactRecord:
        """Insert or authenticate immutable artifact metadata in a caller transaction."""
        existing_identity = connection.execute(
            """
            SELECT * FROM game_artifacts
            WHERE COALESCE(game_id, '') = COALESCE(?, '')
              AND artifact_kind = ? AND content_digest = ?
            """,
            (
                str(request.game_id) if request.game_id else None,
                request.artifact_kind.value,
                request.content_digest,
            ),
        ).fetchone()
        if existing_identity is not None:
            existing = _artifact_from_row(existing_identity)
            if self._artifact_semantics(existing) != self._artifact_semantics(request):
                raise ImmutableRecordError(
                    "Artifact digest identity was reused with different metadata"
                )
            return existing
        existing_id = connection.execute(
            "SELECT * FROM game_artifacts WHERE artifact_id = ?",
            (str(request.artifact_id),),
        ).fetchone()
        if existing_id is not None:
            raise ImmutableRecordError(
                f"Artifact id {request.artifact_id} already identifies different content"
            )
        try:
            connection.execute(
                """
                INSERT INTO game_artifacts(
                    artifact_id, game_id, artifact_kind, schema_version,
                    media_type, uri, byte_size, content_digest, created_at,
                    producer_kind, producer_version
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(request.artifact_id),
                    str(request.game_id) if request.game_id else None,
                    request.artifact_kind.value,
                    request.schema_version,
                    request.media_type,
                    request.uri,
                    request.byte_size,
                    request.content_digest,
                    datetime_to_text(created_at),
                    request.producer_kind.value,
                    request.producer_version,
                ),
            )
        except sqlite3.IntegrityError as exc:
            raise ConflictError(
                f"Artifact {request.artifact_id} could not be published: {exc}"
            ) from exc
        row = self._required_row(
            connection,
            "SELECT * FROM game_artifacts WHERE artifact_id = ?",
            (str(request.artifact_id),),
            "artifact",
        )
        return _artifact_from_row(row)

    def list_artifacts(
        self,
        game_id: UUID,
        *,
        artifact_kind: ArtifactKind | None = None,
    ) -> tuple[ArtifactRecord, ...]:
        """List immutable artifact descriptors for one game."""

        with self._database.read("list_artifacts") as connection:
            if artifact_kind is None:
                rows = connection.execute(
                    "SELECT * FROM game_artifacts WHERE game_id = ? ORDER BY created_at",
                    (str(game_id),),
                ).fetchall()
            else:
                rows = connection.execute(
                    "SELECT * FROM game_artifacts WHERE game_id = ? AND artifact_kind = ? ORDER BY created_at",
                    (str(game_id), artifact_kind.value),
                ).fetchall()
        return tuple(_artifact_from_row(row) for row in rows)

    def publish_summary_correction(
        self,
        summary: GameSummary,
        *,
        summary_revision: int,
        source_event_digest: str,
        source_combat_log_digest: str,
        supersedes_summary_id: UUID | None = None,
        summary_id: UUID | None = None,
    ) -> FinalSummaryRecord:
        """Publish an immutable correction to existing terminal evidence.

        Initial terminal publication has exactly one path:
        :meth:`publish_terminal_evidence`.  Corrections may change derived
        summary facts, but must preserve the replay coordinates fixed by that
        terminal transaction.
        """

        if summary_revision < 2:
            raise ValueError("Summary corrections must start at revision 2")
        try:
            summary_game_id = UUID(summary.game_id)
        except ValueError as exc:
            raise ValueError("Persisted game summaries require a UUID game_id") from exc
        with self._database.transaction("publish_summary_correction") as connection:
            game_row = self._required_row(
                connection,
                "SELECT lifecycle_state FROM games WHERE game_id = ?",
                (str(summary_game_id),),
                "game",
            )
            if GameLifecycleState(game_row["lifecycle_state"]) is not GameLifecycleState.ENDED:
                raise ConflictError(
                    "Summary corrections require terminal replay evidence"
                )
            terminal_artifact_kinds = {
                ArtifactKind(row["artifact_kind"])
                for row in connection.execute(
                    """
                    SELECT artifact_kind FROM game_artifacts
                    WHERE game_id = ? AND artifact_kind IN (?, ?)
                    """,
                    (
                        str(summary_game_id),
                        ArtifactKind.REPLAY_BUNDLE.value,
                        ArtifactKind.SUBJECTIVE_REPLAY_BUNDLE.value,
                    ),
                ).fetchall()
            }
            if terminal_artifact_kinds != {
                ArtifactKind.REPLAY_BUNDLE,
                ArtifactKind.SUBJECTIVE_REPLAY_BUNDLE,
            }:
                raise ConflictError(
                    "Summary corrections require complete terminal replay evidence"
                )
            return self._publish_final_summary_in_transaction(
                connection,
                summary,
                summary_revision=summary_revision,
                source_event_digest=source_event_digest,
                source_combat_log_digest=source_combat_log_digest,
                supersedes_summary_id=supersedes_summary_id,
                summary_id=summary_id,
            )

    def publish_terminal_evidence(
        self,
        replay_artifact: ArtifactCreate,
        summary: GameSummary,
        *,
        additional_artifacts: tuple[ArtifactCreate, ...] = (),
        summary_revision: int,
        source_event_digest: str,
        source_combat_log_digest: str,
        supersedes_summary_id: UUID | None = None,
        summary_id: UUID | None = None,
    ) -> tuple[ArtifactRecord, FinalSummaryRecord]:
        """Atomically publish replay metadata, summary, and the ended transition.

        Replay bytes are persisted by the caller before this transaction. An
        exact retry against an already-ended game is idempotent; no other
        terminal lifecycle may be resurrected as ended.
        """
        try:
            summary_game_id = UUID(summary.game_id)
        except ValueError as exc:
            raise ValueError("Persisted game summaries require a UUID game_id") from exc
        terminal_artifacts = (replay_artifact, *additional_artifacts)
        if any(artifact.game_id != summary_game_id for artifact in terminal_artifacts):
            raise ValueError("Terminal artifacts and summary must belong to the same game")
        if replay_artifact.artifact_kind is not ArtifactKind.REPLAY_BUNDLE:
            raise ValueError("Terminal evidence requires a replay-bundle artifact")
        artifact_kinds = tuple(artifact.artifact_kind for artifact in terminal_artifacts)
        if len(artifact_kinds) != len(set(artifact_kinds)):
            raise ValueError("Terminal evidence artifacts must use distinct artifact kinds")
        with self._database.transaction("publish_terminal_evidence") as connection:
            game_row = self._required_row(
                connection,
                "SELECT * FROM games WHERE game_id = ?",
                (str(summary_game_id),),
                "game",
            )
            lifecycle_state = GameLifecycleState(game_row["lifecycle_state"])
            if lifecycle_state is GameLifecycleState.ENDED:
                result = self._require_exact_terminal_evidence_retry(
                    connection,
                    replay_artifact,
                    summary,
                    additional_artifacts=additional_artifacts,
                    summary_revision=summary_revision,
                    source_event_digest=source_event_digest,
                    source_combat_log_digest=source_combat_log_digest,
                    supersedes_summary_id=supersedes_summary_id,
                )
                active_lease = connection.execute(
                    """
                    SELECT 1 FROM character_deployment_leases
                    WHERE game_id = ? AND released_at IS NULL
                    LIMIT 1
                    """,
                    (str(summary_game_id),),
                ).fetchone()
                if active_lease is not None:
                    raise ConflictError(
                        "Ended terminal game retains an active character lease",
                    )
                return result
            if lifecycle_state is not GameLifecycleState.ACTIVE:
                raise ConflictError(
                    "Terminal evidence can only end an active game"
                )
            if (
                ArtifactKind.SUBJECTIVE_REPLAY_BUNDLE
                not in artifact_kinds
            ):
                raise ValueError(
                    "Terminal evidence requires one subjective replay archive"
                )
            active_lease_ids = {
                UUID(row["lease_id"])
                for row in connection.execute(
                    """
                    SELECT lease_id FROM character_deployment_leases
                    WHERE game_id = ? AND released_at IS NULL
                    """,
                    (str(summary_game_id),),
                ).fetchall()
            }
            if active_lease_ids:
                raise ConflictError(
                    "Generic terminal evidence cannot settle active character "
                    "leases",
                )

            created_at = self._now()
            artifact = self._publish_artifact_in_transaction(
                connection,
                replay_artifact,
                created_at=created_at,
            )
            additional_records = tuple(
                self._publish_artifact_in_transaction(
                    connection,
                    additional_artifact,
                    created_at=created_at,
                )
                for additional_artifact in additional_artifacts
            )
            published_summary = self._publish_final_summary_in_transaction(
                connection,
                summary,
                summary_revision=summary_revision,
                source_event_digest=source_event_digest,
                source_combat_log_digest=source_combat_log_digest,
                supersedes_summary_id=supersedes_summary_id,
                summary_id=summary_id,
                replay_artifact=artifact,
                additional_artifacts=additional_records,
                created_at=created_at,
            )
            return artifact, published_summary

    def finalize_staged_local_terminal_commit(
        self,
        replay_artifact: ArtifactCreate,
        summary: GameSummary,
        *,
        additional_artifacts: tuple[ArtifactCreate, ...],
        summary_revision: int,
        source_event_digest: str,
        source_combat_log_digest: str,
        payload_digest: str,
        settlement_bundle: CharacterRevisionBundleCommit | None,
        lease_id: UUID | None,
    ) -> tuple[ArtifactRecord, FinalSummaryRecord]:
        """Atomically publish terminal evidence, settlement, and lease release."""

        try:
            game_id = UUID(summary.game_id)
        except ValueError as exc:
            raise ValueError(
                "Persisted game summaries require a UUID game_id",
            ) from exc
        terminal_artifacts = (replay_artifact, *additional_artifacts)
        if any(artifact.game_id != game_id for artifact in terminal_artifacts):
            raise ValueError(
                "Terminal artifacts and summary must belong to the same game",
            )
        if replay_artifact.artifact_kind is not ArtifactKind.REPLAY_BUNDLE:
            raise ValueError(
                "Terminal evidence requires a replay-bundle artifact",
            )
        artifact_kinds = tuple(
            artifact.artifact_kind for artifact in terminal_artifacts
        )
        if len(artifact_kinds) != len(set(artifact_kinds)):
            raise ValueError(
                "Terminal evidence artifacts must use distinct artifact kinds",
            )
        if ArtifactKind.SUBJECTIVE_REPLAY_BUNDLE not in artifact_kinds:
            raise ValueError(
                "Terminal evidence requires one subjective replay archive",
            )
        if (settlement_bundle is None) != (lease_id is None):
            raise ValueError(
                "Character settlement bundle and lease must be supplied "
                "together",
            )

        with self._database.transaction(
            "finalize_staged_local_terminal_commit",
        ) as connection:
            intent = self._required_row(
                connection,
                """
                SELECT * FROM local_terminal_commit_intents
                WHERE game_id = ?
                """,
                (str(game_id),),
                "local terminal commit intent",
            )
            if (
                intent["payload_digest"] != payload_digest
                or intent["lease_id"]
                != (str(lease_id) if lease_id is not None else None)
            ):
                raise ImmutableRecordError(
                    "Local terminal commit intent differs from finalization",
                )
            game_row = self._required_row(
                connection,
                "SELECT * FROM games WHERE game_id = ?",
                (str(game_id),),
                "game",
            )
            lifecycle_state = GameLifecycleState(
                game_row["lifecycle_state"],
            )
            if intent["committed_at"] is not None:
                artifact, published = (
                    self._require_exact_terminal_evidence_retry(
                        connection,
                        replay_artifact,
                        summary,
                        additional_artifacts=additional_artifacts,
                        summary_revision=summary_revision,
                        source_event_digest=source_event_digest,
                        source_combat_log_digest=source_combat_log_digest,
                        supersedes_summary_id=None,
                    )
                )
                if settlement_bundle is not None and lease_id is not None:
                    self._require_exact_terminal_settlement_retry(
                        connection,
                        settlement_bundle,
                        lease_id=lease_id,
                        release_reason="local_game_settled",
                    )
                if connection.execute(
                    """
                    SELECT 1 FROM character_deployment_leases
                    WHERE game_id = ? AND released_at IS NULL
                    LIMIT 1
                    """,
                    (str(game_id),),
                ).fetchone() is not None:
                    raise ConflictError(
                        "Committed local terminal game retains an active "
                        "character lease",
                    )
                return artifact, published
            if lifecycle_state is not GameLifecycleState.ACTIVE:
                raise ConflictError(
                    "Staged local terminal commit requires an active game",
                )
            active_lease_ids = {
                UUID(row["lease_id"])
                for row in connection.execute(
                    """
                    SELECT lease_id FROM character_deployment_leases
                    WHERE game_id = ? AND released_at IS NULL
                    """,
                    (str(game_id),),
                ).fetchall()
            }
            expected_lease_ids = (
                {lease_id} if lease_id is not None else set()
            )
            if active_lease_ids != expected_lease_ids:
                raise ConflictError(
                    "Local terminal commit does not account for every active "
                    "character lease",
                )

            created_at = self._now()
            artifact = self._publish_artifact_in_transaction(
                connection,
                replay_artifact,
                created_at=created_at,
            )
            additional_records = tuple(
                self._publish_artifact_in_transaction(
                    connection,
                    additional_artifact,
                    created_at=created_at,
                )
                for additional_artifact in additional_artifacts
            )
            published = self._publish_final_summary_in_transaction(
                connection,
                summary,
                summary_revision=summary_revision,
                source_event_digest=source_event_digest,
                source_combat_log_digest=source_combat_log_digest,
                supersedes_summary_id=None,
                summary_id=None,
                replay_artifact=artifact,
                additional_artifacts=additional_records,
                created_at=created_at,
            )
            if settlement_bundle is not None and lease_id is not None:
                self._commit_terminal_settlement_in_transaction(
                    connection,
                    settlement_bundle,
                    lease_id=lease_id,
                    created_at=created_at,
                    release_reason="local_game_settled",
                )
            connection.execute(
                """
                UPDATE local_terminal_commit_intents
                SET committed_at = ?
                WHERE game_id = ? AND committed_at IS NULL
                """,
                (datetime_to_text(created_at), str(game_id)),
            )
            return artifact, published

    def finalize_staged_worker_terminal_commit(
        self,
        replay_artifact: ArtifactCreate,
        summary: GameSummary,
        *,
        subjective_artifact: ArtifactCreate,
        summary_revision: int,
        source_event_digest: str,
        source_combat_log_digest: str,
        manifest_digest: str,
        summary_evidence: JsonObject,
        settlement_evidence: JsonObject | None,
        settlement_bundle: CharacterRevisionBundleCommit | None,
        lease_id: UUID | None,
    ) -> tuple[ArtifactRecord, FinalSummaryRecord]:
        """Atomically adopt one staged hosted terminal ready manifest."""

        try:
            game_id = UUID(summary.game_id)
        except ValueError as exc:
            raise ValueError(
                "Persisted game summaries require a UUID game_id",
            ) from exc
        if (
            replay_artifact.game_id != game_id
            or subjective_artifact.game_id != game_id
        ):
            raise ValueError(
                "Terminal artifacts and summary must belong to the same game",
            )
        if replay_artifact.artifact_kind is not ArtifactKind.REPLAY_BUNDLE:
            raise ValueError(
                "Hosted terminal evidence requires an objective replay",
            )
        if (
            subjective_artifact.artifact_kind
            is not ArtifactKind.SUBJECTIVE_REPLAY_BUNDLE
        ):
            raise ValueError(
                "Hosted terminal evidence requires a subjective replay",
            )
        if (settlement_bundle is None) != (lease_id is None):
            raise ValueError(
                "Hosted character settlement bundle and lease must be "
                "supplied together",
            )
        if (settlement_evidence is None) != (settlement_bundle is None):
            raise ValueError(
                "Hosted settlement evidence and settlement bundle must be "
                "supplied together",
            )

        with self._database.transaction(
            "finalize_staged_worker_terminal_commit",
        ) as connection:
            row = self._required_row(
                connection,
                """
                SELECT * FROM worker_terminal_ready_manifests
                WHERE game_id = ?
                """,
                (str(game_id),),
                "worker terminal ready manifest",
            )
            manifest = _worker_terminal_ready_manifest_from_row(row)
            if (
                manifest.manifest_digest != manifest_digest
                or manifest.objective_artifact.model_dump()
                != replay_artifact.model_dump()
                or manifest.subjective_artifact.model_dump()
                != subjective_artifact.model_dump()
                or manifest.summary_evidence != summary_evidence
                or manifest.settlement_evidence != settlement_evidence
            ):
                raise ImmutableRecordError(
                    "Hosted terminal finalization differs from its ready "
                    "manifest",
                )
            game_row = self._required_row(
                connection,
                "SELECT * FROM games WHERE game_id = ?",
                (str(game_id),),
                "game",
            )
            lifecycle_state = GameLifecycleState(
                game_row["lifecycle_state"],
            )
            if manifest.adopted_at is not None:
                artifact, published = self._require_exact_terminal_evidence_retry(
                    connection,
                    replay_artifact,
                    summary,
                    additional_artifacts=(subjective_artifact,),
                    summary_revision=summary_revision,
                    source_event_digest=source_event_digest,
                    source_combat_log_digest=source_combat_log_digest,
                    supersedes_summary_id=None,
                )
                if settlement_bundle is not None and lease_id is not None:
                    self._require_exact_terminal_settlement_retry(
                        connection,
                        settlement_bundle,
                        lease_id=lease_id,
                        release_reason="hosted_game_settled",
                    )
                if connection.execute(
                    """
                    SELECT 1 FROM character_deployment_leases
                    WHERE game_id = ? AND released_at IS NULL
                    LIMIT 1
                    """,
                    (str(game_id),),
                ).fetchone() is not None:
                    raise ConflictError(
                        "Adopted hosted terminal game retains an active "
                        "character lease",
                    )
                return artifact, published
            if lifecycle_state is not GameLifecycleState.ACTIVE:
                raise ConflictError(
                    "Hosted terminal manifest requires an active game",
                )
            active_lease_ids = {
                UUID(active["lease_id"])
                for active in connection.execute(
                    """
                    SELECT lease_id FROM character_deployment_leases
                    WHERE game_id = ? AND released_at IS NULL
                    """,
                    (str(game_id),),
                ).fetchall()
            }
            expected_lease_ids = (
                {lease_id} if lease_id is not None else set()
            )
            if active_lease_ids != expected_lease_ids:
                raise ConflictError(
                    "Hosted terminal manifest does not account for every "
                    "active character lease",
                )

            created_at = self._now()
            artifact = self._publish_artifact_in_transaction(
                connection,
                replay_artifact,
                created_at=created_at,
            )
            subjective_record = self._publish_artifact_in_transaction(
                connection,
                subjective_artifact,
                created_at=created_at,
            )
            published = self._publish_final_summary_in_transaction(
                connection,
                summary,
                summary_revision=summary_revision,
                source_event_digest=source_event_digest,
                source_combat_log_digest=source_combat_log_digest,
                supersedes_summary_id=None,
                summary_id=None,
                replay_artifact=artifact,
                additional_artifacts=(subjective_record,),
                created_at=created_at,
            )
            if settlement_bundle is not None and lease_id is not None:
                self._commit_terminal_settlement_in_transaction(
                    connection,
                    settlement_bundle,
                    lease_id=lease_id,
                    created_at=created_at,
                    release_reason="hosted_game_settled",
                )
            connection.execute(
                """
                UPDATE worker_terminal_ready_manifests
                SET adopted_at = ?
                WHERE game_id = ? AND adopted_at IS NULL
                """,
                (datetime_to_text(created_at), str(game_id)),
            )
            return artifact, published

    def _commit_terminal_settlement_in_transaction(
        self,
        connection: sqlite3.Connection,
        request: CharacterRevisionBundleCommit,
        *,
        lease_id: UUID,
        created_at: datetime,
        release_reason: str,
    ) -> CanonicalCharacterRecord:
        """Commit one holdings settlement inside terminal publication."""

        if not release_reason:
            raise ValueError("terminal settlement release reason cannot be empty")
        if (
            request.new_holdings is None
            or request.settlement is None
            or request.new_definition is not None
            or request.new_loadout is not None
            or request.advancement_award is not None
            or request.mutation_receipt is not None
        ):
            raise ValueError(
                "Terminal settlement must contain only holdings and "
                "its settlement receipt",
            )
        settlement = request.settlement
        holdings = request.new_holdings
        current_row = self._required_row(
            connection,
            "SELECT * FROM characters WHERE character_id = ?",
            (str(request.character_id),),
            "character",
        )
        current = _canonical_character_from_row(current_row)
        expected = request.expected_heads
        if (
            current.row_version != request.expected_row_version
            or current.current_definition_revision
            != expected.definition_revision
            or current.current_definition_digest
            != expected.definition_digest
            or current.current_holdings_revision
            != expected.holdings_revision
            or current.current_holdings_digest != expected.holdings_digest
            or current.current_loadout_revision
            != expected.loadout_revision
            or current.current_loadout_digest != expected.loadout_digest
        ):
            raise StaleVersionError(
                f"Character {request.character_id} revision heads changed",
            )
        deployment = self._required_row(
            connection,
            """
            SELECT * FROM character_deployments
            WHERE deployment_id = ?
            """,
            (str(settlement.deployment_id),),
            "character deployment",
        )
        if (
            deployment["game_id"] != str(settlement.game_id)
            or deployment["character_id"] != str(settlement.character_id)
            or deployment["lease_id"] != str(lease_id)
            or deployment["pin_state"] != "pinned"
        ):
            raise ConflictError(
                "Terminal settlement does not match its pinned "
                "deployment",
            )
        timestamp = datetime_to_text(created_at)
        try:
            connection.execute(
                """
                INSERT INTO character_holdings_revisions(
                    character_id, holdings_revision, schema_version,
                    holdings_json, holdings_digest, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    str(holdings.character_id),
                    holdings.holdings_revision,
                    holdings.schema_version,
                    canonical_json(holdings.model_dump(mode="json")),
                    holdings.holdings_digest,
                    timestamp,
                ),
            )
            cursor = connection.execute(
                """
                UPDATE characters
                SET current_holdings_revision = ?,
                    current_holdings_digest = ?,
                    updated_at = ?,
                    row_version = row_version + 1
                WHERE character_id = ?
                  AND current_holdings_revision = ?
                  AND current_holdings_digest = ?
                  AND row_version = ?
                """,
                (
                    holdings.holdings_revision,
                    holdings.holdings_digest,
                    timestamp,
                    str(request.character_id),
                    expected.holdings_revision,
                    expected.holdings_digest,
                    request.expected_row_version,
                ),
            )
            if cursor.rowcount != 1:
                raise StaleVersionError(
                    f"Character {request.character_id} revision heads changed",
                )
            connection.execute(
                """
                INSERT INTO character_settlements(
                    settlement_id, deployment_id, game_id, character_id,
                    starting_holdings_revision, starting_holdings_digest,
                    resulting_holdings_revision, resulting_holdings_digest,
                    delta_digest, settled_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(settlement.settlement_id),
                    str(settlement.deployment_id),
                    str(settlement.game_id),
                    str(settlement.character_id),
                    settlement.starting_holdings_revision,
                    settlement.starting_holdings_digest,
                    settlement.resulting_holdings_revision,
                    settlement.resulting_holdings_digest,
                    settlement.delta_digest,
                    timestamp,
                ),
            )
            lease = self._required_row(
                connection,
                """
                SELECT * FROM character_deployment_leases
                WHERE lease_id = ?
                """,
                (str(lease_id),),
                "character deployment lease",
            )
            if lease["released_at"] is not None:
                raise ConflictError(
                    "Terminal character lease was already released",
                )
            connection.execute(
                """
                UPDATE character_deployment_leases
                SET released_at = ?, release_reason = ?
                WHERE lease_id = ? AND released_at IS NULL
                """,
                (timestamp, release_reason, str(lease_id)),
            )
        except sqlite3.IntegrityError as exc:
            raise ConflictError(
                f"Terminal settlement failed: {exc}",
            ) from exc
        updated = self._required_row(
            connection,
            "SELECT * FROM characters WHERE character_id = ?",
            (str(request.character_id),),
            "character",
        )
        return _canonical_character_from_row(updated)

    def _require_exact_terminal_settlement_retry(
        self,
        connection: sqlite3.Connection,
        request: CharacterRevisionBundleCommit,
        *,
        lease_id: UUID,
        release_reason: str,
    ) -> None:
        """Authenticate a fully committed terminal settlement retry."""

        settlement = request.settlement
        holdings = request.new_holdings
        if settlement is None or holdings is None:
            raise ValueError(
                "Terminal settlement retry requires holdings evidence",
            )
        row = self._required_row(
            connection,
            """
            SELECT * FROM character_settlements
            WHERE deployment_id = ?
            """,
            (str(settlement.deployment_id),),
            "character settlement",
        )
        existing = _character_settlement_from_row(row)
        if (
            existing.model_dump(exclude={"settled_at"})
            != settlement.model_dump()
        ):
            raise ConflictError(
                "Terminal settlement retry changed its evidence",
            )
        holdings_row = self._required_row(
            connection,
            """
            SELECT holdings_digest FROM character_holdings_revisions
            WHERE character_id = ? AND holdings_revision = ?
            """,
            (
                str(holdings.character_id),
                holdings.holdings_revision,
            ),
            "character holdings revision",
        )
        if holdings_row["holdings_digest"] != holdings.holdings_digest:
            raise ConflictError(
                "Terminal settlement retry changed holdings",
            )
        lease = self._required_row(
            connection,
            """
            SELECT released_at, release_reason
            FROM character_deployment_leases WHERE lease_id = ?
            """,
            (str(lease_id),),
            "character deployment lease",
        )
        if (
            lease["released_at"] is None
            or lease["release_reason"] != release_reason
        ):
            raise ConflictError(
                "Terminal settlement retry has an unreleased lease",
            )

    def _require_exact_terminal_evidence_retry(
        self,
        connection: sqlite3.Connection,
        replay_artifact: ArtifactCreate,
        summary: GameSummary,
        *,
        additional_artifacts: tuple[ArtifactCreate, ...],
        summary_revision: int,
        source_event_digest: str,
        source_combat_log_digest: str,
        supersedes_summary_id: UUID | None,
    ) -> tuple[ArtifactRecord, FinalSummaryRecord]:
        """Authenticate a complete already-published terminal evidence pair."""
        artifact = self._require_exact_terminal_artifact_retry(
            connection,
            replay_artifact,
        )
        for additional_artifact in additional_artifacts:
            self._require_exact_terminal_artifact_retry(
                connection,
                additional_artifact,
            )

        persisted_subjective_count = int(
            connection.execute(
                """
                SELECT COUNT(*) FROM game_artifacts
                WHERE game_id = ? AND artifact_kind = ?
                """,
                (
                    str(replay_artifact.game_id),
                    ArtifactKind.SUBJECTIVE_REPLAY_BUNDLE.value,
                ),
            ).fetchone()[0]
        )
        requested_subjective_count = sum(
            artifact.artifact_kind is ArtifactKind.SUBJECTIVE_REPLAY_BUNDLE
            for artifact in additional_artifacts
        )
        if persisted_subjective_count != requested_subjective_count:
            raise ConflictError(
                "Ended game subjective replay evidence differs from the exact retry"
            )

        summary_row = connection.execute(
            "SELECT * FROM game_summaries WHERE game_id = ? AND summary_digest = ?",
            (summary.game_id, summary.canonical_sha256),
        ).fetchone()
        if summary_row is None:
            raise ConflictError("Ended game is missing the exact final summary")
        published = _summary_from_row(summary_row)
        if (
            published.summary_revision != summary_revision
            or published.source_event_digest != source_event_digest
            or published.source_combat_log_digest != source_combat_log_digest
            or published.supersedes_summary_id != supersedes_summary_id
        ):
            raise ImmutableRecordError(
                "Summary retry changed revision or source evidence"
            )
        return artifact, published

    def _require_exact_terminal_artifact_retry(
        self,
        connection: sqlite3.Connection,
        request: ArtifactCreate,
    ) -> ArtifactRecord:
        """Authenticate one immutable artifact in an already-ended retry."""

        artifact_row = connection.execute(
            """
            SELECT * FROM game_artifacts
            WHERE game_id = ? AND artifact_kind = ? AND content_digest = ?
            """,
            (
                str(request.game_id),
                request.artifact_kind.value,
                request.content_digest,
            ),
        ).fetchone()
        if artifact_row is None:
            raise ConflictError("Ended game is missing an exact terminal artifact")
        artifact = _artifact_from_row(artifact_row)
        if self._artifact_semantics(artifact) != self._artifact_semantics(request):
            raise ImmutableRecordError(
                "Terminal artifact retry changed immutable metadata"
            )
        return artifact

    def _publish_final_summary_in_transaction(
        self,
        connection: sqlite3.Connection,
        summary: GameSummary,
        *,
        summary_revision: int,
        source_event_digest: str,
        source_combat_log_digest: str,
        supersedes_summary_id: UUID | None,
        summary_id: UUID | None,
        replay_artifact: ArtifactRecord | None = None,
        additional_artifacts: tuple[ArtifactRecord, ...] = (),
        created_at: datetime | None = None,
    ) -> FinalSummaryRecord:
        """Insert one final-summary revision inside a caller-owned transaction."""

        if summary_revision < 1:
            raise ValueError("summary_revision must be positive")
        if not source_event_digest or not source_combat_log_digest:
            raise ValueError("Summary source digests cannot be empty")
        try:
            summary_game_id = UUID(summary.game_id)
        except ValueError as exc:
            raise ValueError("Persisted game summaries require a UUID game_id") from exc
        if summary.started_at is None or summary.ended_at is None:
            raise ValueError("Persisted terminal summaries require start and end timestamps")
        winner_side_id = (
            summary.outcome.winning_side_ids[0]
            if len(summary.outcome.winning_side_ids) == 1
            else None
        )
        terminal_reason = summary.outcome.reason or summary.outcome.resolution.value
        turn_count = sum(entity.statistics.turns_started for entity in summary.entities)
        duration_ms = round((summary.duration_seconds or 0.0) * 1000)
        schema_version = f"{summary.schema_name}.v{summary.schema_version}"
        now = created_at or self._now()
        if not summary_digest_is_valid(summary):
            raise ValueError("Canonical game-summary digest is invalid")
        summary_json = canonical_json(summary)
        summary_digest = summary.canonical_sha256
        resolved_summary_id = summary_id or uuid4()
        self._required_row(
            connection,
            "SELECT game_id FROM games WHERE game_id = ?",
            (str(summary_game_id),),
            "game",
        )
        identical_row = connection.execute(
            "SELECT * FROM game_summaries WHERE game_id = ? AND summary_digest = ?",
            (str(summary_game_id), summary_digest),
        ).fetchone()
        if identical_row is not None:
            identical = _summary_from_row(identical_row)
            if (
                identical.summary_revision != summary_revision
                or identical.source_event_digest != source_event_digest
                or identical.source_combat_log_digest != source_combat_log_digest
                or identical.supersedes_summary_id != supersedes_summary_id
            ):
                raise ImmutableRecordError(
                    "Summary digest was reused with different revision or source evidence"
                )
            return identical

        revision_row = connection.execute(
            "SELECT * FROM game_summaries WHERE game_id = ? AND summary_revision = ?",
            (str(summary_game_id), summary_revision),
        ).fetchone()
        if revision_row is not None:
            raise ImmutableRecordError(
                f"Summary revision {summary_revision} already contains different content"
            )

        current_row = connection.execute(
            "SELECT * FROM game_summaries WHERE game_id = ? AND is_current = 1",
            (str(summary_game_id),),
        ).fetchone()
        if current_row is None:
            if summary_revision != 1 or supersedes_summary_id is not None:
                raise ImmutableRecordError(
                    "The first summary must be revision 1 and cannot supersede another summary"
                )
        else:
            current = _summary_from_row(current_row)
            if (
                current.summary.encounter_uuid != summary.encounter_uuid
                or current.summary.terminal_cursor != summary.terminal_cursor
            ):
                raise ImmutableRecordError(
                    "Summary corrections cannot change terminal replay coordinates"
                )
            if summary_revision != current.summary_revision + 1:
                raise ImmutableRecordError("Summary revisions must increase by exactly one")
            if supersedes_summary_id != current.summary_id:
                raise ImmutableRecordError(
                    "A correction must explicitly supersede the current summary"
                )
            connection.execute(
                "UPDATE game_summaries SET is_current = 0 WHERE summary_id = ?",
                (str(current.summary_id),),
            )

        try:
            connection.execute(
                """
                INSERT INTO game_summaries(
                    summary_id, game_id, schema_version, summary_revision,
                    summary_json, summary_digest, winner_side_id,
                    terminal_reason, round_count, turn_count, duration_ms,
                    source_event_digest, source_combat_log_digest, created_at,
                    supersedes_summary_id, is_current
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
                """,
                (
                    str(resolved_summary_id),
                    str(summary_game_id),
                    schema_version,
                    summary_revision,
                    summary_json,
                    summary_digest,
                    winner_side_id,
                    terminal_reason,
                    summary.rounds_started,
                    turn_count,
                    duration_ms,
                    source_event_digest,
                    source_combat_log_digest,
                    datetime_to_text(now),
                    str(supersedes_summary_id) if supersedes_summary_id else None,
                ),
            )
        except sqlite3.IntegrityError as exc:
            raise ConflictError(f"Summary could not be published: {exc}") from exc

        connection.execute(
            """
            UPDATE games
            SET lifecycle_state = 'ended', ended_at = ?, terminal_reason = ?,
                winner_side_id = ?, final_event_cursor = ?,
                final_combat_log_cursor = ?, current_summary_digest = ?,
                row_version = row_version + 1
            WHERE game_id = ?
            """,
            (
                datetime_to_text(summary.ended_at),
                terminal_reason,
                winner_side_id,
                summary.terminal_cursor.event_cursor,
                summary.terminal_cursor.combat_log_cursor,
                summary_digest,
                str(summary_game_id),
            ),
        )
        event_payload = {
            "summary_id": str(resolved_summary_id),
            "summary_revision": summary_revision,
            "summary_digest": summary_digest,
            "schema_version": schema_version,
        }
        if replay_artifact is not None:
            event_payload.update(
                {
                    "replay_artifact_id": str(replay_artifact.artifact_id),
                    "replay_digest": replay_artifact.content_digest,
                    "replay_schema_version": replay_artifact.schema_version,
                }
            )
        if additional_artifacts:
            event_payload["additional_artifacts"] = [
                {
                    "artifact_id": str(artifact.artifact_id),
                    "artifact_kind": artifact.artifact_kind.value,
                    "content_digest": artifact.content_digest,
                    "schema_version": artifact.schema_version,
                }
                for artifact in additional_artifacts
            ]
        self._append_event_in_transaction(
            connection,
            game_id=summary_game_id,
            event_type="summary_ready",
            payload=event_payload,
            created_at=now,
        )
        row = self._required_row(
            connection,
            "SELECT * FROM game_summaries WHERE summary_id = ?",
            (str(resolved_summary_id),),
            "game summary",
        )
        return _summary_from_row(row)

    def get_current_summary(self, game_id: UUID) -> FinalSummaryRecord:
        """Return the current immutable summary revision for a game."""

        with self._database.read("get_current_summary") as connection:
            row = self._required_row(
                connection,
                "SELECT * FROM game_summaries WHERE game_id = ? AND is_current = 1",
                (str(game_id),),
                "current game summary",
            )
        return _summary_from_row(row)

    def list_summaries(self, game_id: UUID) -> tuple[FinalSummaryRecord, ...]:
        """List all immutable summary revisions for a game."""

        with self._database.read("list_summaries") as connection:
            rows = connection.execute(
                "SELECT * FROM game_summaries WHERE game_id = ? ORDER BY summary_revision",
                (str(game_id),),
            ).fetchall()
        return tuple(_summary_from_row(row) for row in rows)

    def create_rating_run(self, request: RatingRunCreate) -> RatingRunRecord:
        """Persist an immutable rating-run definition."""

        now = self._now()
        parameters_json = canonical_json(request.parameters)
        selection_json = canonical_json(request.selection_query)
        compatibility_json = canonical_json(request.compatibility_constraints)
        with self._database.transaction("create_rating_run") as connection:
            try:
                connection.execute(
                    """
                    INSERT INTO rating_runs(
                        rating_run_id, algorithm_id, algorithm_version,
                        parameters_json, parameters_digest, selection_query_json,
                        selection_query_digest, compatibility_constraints_json,
                        compatibility_digest, status, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(request.rating_run_id),
                        request.algorithm_id,
                        request.algorithm_version,
                        parameters_json,
                        canonical_digest(request.parameters),
                        selection_json,
                        canonical_digest(request.selection_query),
                        compatibility_json,
                        canonical_digest(request.compatibility_constraints),
                        RatingRunStatus.RESERVED.value,
                        datetime_to_text(now),
                    ),
                )
            except sqlite3.IntegrityError as exc:
                raise ConflictError(f"Rating run {request.rating_run_id} already exists") from exc
            row = self._required_row(
                connection,
                "SELECT * FROM rating_runs WHERE rating_run_id = ?",
                (str(request.rating_run_id),),
                "rating run",
            )
        return _rating_run_from_row(row)

    def get_rating_run(self, rating_run_id: UUID) -> RatingRunRecord:
        """Return one rating-run definition and lifecycle record."""

        with self._database.read("get_rating_run") as connection:
            row = self._required_row(
                connection,
                "SELECT * FROM rating_runs WHERE rating_run_id = ?",
                (str(rating_run_id),),
                "rating run",
            )
        return _rating_run_from_row(row)

    def set_rating_run_status(
        self,
        rating_run_id: UUID,
        *,
        status: RatingRunStatus,
        output_artifact_digest: str | None = None,
    ) -> RatingRunRecord:
        """Advance rating-run lifecycle without mutating its definition."""

        now = self._now()
        completed_at = now if status in {RatingRunStatus.COMPLETED, RatingRunStatus.FAILED} else None
        with self._database.transaction("set_rating_run_status") as connection:
            cursor = connection.execute(
                """
                UPDATE rating_runs
                SET status = ?, completed_at = ?, output_artifact_digest = ?
                WHERE rating_run_id = ?
                """,
                (
                    status.value,
                    _optional_text(completed_at),
                    output_artifact_digest,
                    str(rating_run_id),
                ),
            )
            if cursor.rowcount != 1:
                raise NotFoundError(f"Rating run {rating_run_id} does not exist")
            row = self._required_row(
                connection,
                "SELECT * FROM rating_runs WHERE rating_run_id = ?",
                (str(rating_run_id),),
                "rating run",
            )
        return _rating_run_from_row(row)

    def add_rating_admission(
        self,
        request: RatingAdmissionCreate,
        *,
        admission_id: UUID | None = None,
    ) -> RatingAdmissionRecord:
        """Record an immutable admission decision for exact game evidence."""

        now = self._now()
        resolved_admission_id = admission_id or uuid4()
        with self._database.transaction("add_rating_admission") as connection:
            existing_row = connection.execute(
                """
                SELECT * FROM rating_admissions
                WHERE rating_run_id = ? AND game_id = ? AND summary_digest = ?
                  AND treatment_id = ? AND configuration_id = ?
                """,
                (
                    str(request.rating_run_id),
                    str(request.game_id),
                    request.summary_digest,
                    request.treatment_id,
                    request.configuration_id,
                ),
            ).fetchone()
            if existing_row is not None:
                existing = _rating_admission_from_row(existing_row)
                if self._admission_semantics(existing) != self._admission_semantics(request):
                    raise ImmutableRecordError("Rating admission identity has different semantics")
                return existing
            try:
                connection.execute(
                    """
                    INSERT INTO rating_admissions(
                        admission_id, rating_run_id, game_id, summary_digest,
                        admitted, exclusion_reason_code, exclusion_detail_json,
                        treatment_id, configuration_id, weight, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(resolved_admission_id),
                        str(request.rating_run_id),
                        str(request.game_id),
                        request.summary_digest,
                        int(request.admitted),
                        request.exclusion_reason_code,
                        canonical_json(request.exclusion_detail),
                        request.treatment_id,
                        request.configuration_id,
                        request.weight,
                        datetime_to_text(now),
                    ),
                )
            except sqlite3.IntegrityError as exc:
                raise ConflictError(f"Rating admission could not be recorded: {exc}") from exc
            row = self._required_row(
                connection,
                "SELECT * FROM rating_admissions WHERE admission_id = ?",
                (str(resolved_admission_id),),
                "rating admission",
            )
        return _rating_admission_from_row(row)

    def list_rating_admissions(self, rating_run_id: UUID) -> tuple[RatingAdmissionRecord, ...]:
        """List immutable evidence decisions for one rating run."""

        with self._database.read("list_rating_admissions") as connection:
            rows = connection.execute(
                "SELECT * FROM rating_admissions WHERE rating_run_id = ? ORDER BY created_at",
                (str(rating_run_id),),
            ).fetchall()
        return tuple(_rating_admission_from_row(row) for row in rows)

    def publish_rating_estimate(
        self,
        request: RatingEstimateCreate,
        *,
        estimate_id: UUID | None = None,
    ) -> RatingEstimateRecord:
        """Publish one immutable subject estimate idempotently."""

        now = self._now()
        resolved_estimate_id = estimate_id or uuid4()
        with self._database.transaction("publish_rating_estimate") as connection:
            existing_row = connection.execute(
                "SELECT * FROM rating_estimates WHERE rating_run_id = ? AND subject_id = ?",
                (str(request.rating_run_id), request.subject_id),
            ).fetchone()
            if existing_row is not None:
                existing = _rating_estimate_from_row(existing_row)
                if self._estimate_semantics(existing) != self._estimate_semantics(request):
                    raise ImmutableRecordError("Rating estimate subject already has different output")
                return existing
            diagnostics_json = canonical_json(request.diagnostics)
            diagnostics_digest = canonical_digest(request.diagnostics)
            try:
                connection.execute(
                    """
                    INSERT INTO rating_estimates(
                        estimate_id, rating_run_id, subject_id, estimate,
                        uncertainty, games, wins, losses, draws, rank,
                        diagnostics_json, diagnostics_digest, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(resolved_estimate_id),
                        str(request.rating_run_id),
                        request.subject_id,
                        request.estimate,
                        request.uncertainty,
                        request.games,
                        request.wins,
                        request.losses,
                        request.draws,
                        request.rank,
                        diagnostics_json,
                        diagnostics_digest,
                        datetime_to_text(now),
                    ),
                )
            except sqlite3.IntegrityError as exc:
                raise ConflictError(f"Rating estimate could not be published: {exc}") from exc
            row = self._required_row(
                connection,
                "SELECT * FROM rating_estimates WHERE estimate_id = ?",
                (str(resolved_estimate_id),),
                "rating estimate",
            )
        return _rating_estimate_from_row(row)

    def list_rating_estimates(self, rating_run_id: UUID) -> tuple[RatingEstimateRecord, ...]:
        """List estimates for one rating run in rank and subject order."""

        with self._database.read("list_rating_estimates") as connection:
            rows = connection.execute(
                """
                SELECT * FROM rating_estimates
                WHERE rating_run_id = ?
                ORDER BY CASE WHEN rank IS NULL THEN 1 ELSE 0 END, rank, subject_id
                """,
                (str(rating_run_id),),
            ).fetchall()
        return tuple(_rating_estimate_from_row(row) for row in rows)

    def _insert_character_advancement_award(
        self,
        connection: sqlite3.Connection,
        request: CharacterAdvancementAwardCreate,
        *,
        created_at: datetime,
    ) -> sqlite3.Row:
        """Insert one award or return its exact natural-key retry."""

        existing = connection.execute(
            """
            SELECT * FROM character_advancement_awards
            WHERE character_id = ? AND source_kind = ? AND source_id = ?
            """,
            (
                str(request.character_id),
                request.source_kind.value,
                request.source_id,
            ),
        ).fetchone()
        if existing is not None:
            if existing["level_delta"] != request.level_delta:
                raise ConflictError(
                    "Advancement source was already recorded with a "
                    "different level delta",
                )
            return existing
        conflicting_id = connection.execute(
            """
            SELECT * FROM character_advancement_awards
            WHERE award_id = ?
            """,
            (str(request.award_id),),
        ).fetchone()
        if conflicting_id is not None:
            raise ConflictError(
                "Advancement award identifier was already used for another "
                "source",
            )
        try:
            connection.execute(
                """
                INSERT INTO character_advancement_awards(
                    award_id, character_id, level_delta,
                    source_kind, source_id, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    str(request.award_id),
                    str(request.character_id),
                    request.level_delta,
                    request.source_kind.value,
                    request.source_id,
                    datetime_to_text(created_at),
                ),
            )
        except sqlite3.IntegrityError as exc:
            raise ConflictError(
                f"Character advancement award could not be created: {exc}",
            ) from exc
        return self._required_row(
            connection,
            "SELECT * FROM character_advancement_awards WHERE award_id = ?",
            (str(request.award_id),),
            "character advancement award",
        )

    def _now(self) -> datetime:
        """Return a validated timezone-aware UTC clock value."""

        value = self._clock()
        if value.tzinfo is None:
            raise ValueError("Directory clock must return timezone-aware datetimes")
        return value.astimezone(UTC)

    @staticmethod
    def _required_row(
        connection: sqlite3.Connection,
        query: str,
        parameters: tuple[object, ...],
        record_name: str,
    ) -> sqlite3.Row:
        """Execute a lookup and raise a typed missing-record failure."""

        row = connection.execute(query, parameters).fetchone()
        if row is None:
            raise NotFoundError(f"Requested {record_name} does not exist")
        return row

    @staticmethod
    def _validate_worker_binding(
        connection: sqlite3.Connection,
        worker_id: UUID | None,
        worker_generation: int | None,
    ) -> None:
        """Validate an optional worker identity and generation pair."""

        if (worker_id is None) != (worker_generation is None):
            raise ConflictError("worker_id and worker_generation must be supplied together")
        if worker_id is None:
            return
        row = connection.execute(
            "SELECT worker_generation FROM workers WHERE worker_id = ?",
            (str(worker_id),),
        ).fetchone()
        if row is None:
            raise NotFoundError(f"Worker {worker_id} does not exist")
        if row["worker_generation"] != worker_generation:
            raise StaleVersionError(
                f"Worker {worker_id} generation is {row['worker_generation']}, expected {worker_generation}"
            )

    @staticmethod
    def _validate_grant_scope(
        connection: sqlite3.Connection,
        request: AccessGrantCreate,
    ) -> None:
        """Ensure optional grant identities belong to the scoped game."""

        GameDirectoryRepository._required_row(
            connection,
            "SELECT game_id FROM games WHERE game_id = ?",
            (str(request.game_id),),
            "game",
        )
        if request.membership_id is not None:
            row = GameDirectoryRepository._required_row(
                connection,
                "SELECT game_id FROM game_memberships WHERE membership_id = ?",
                (str(request.membership_id),),
                "membership",
            )
            if row["game_id"] != str(request.game_id):
                raise ConflictError("Grant membership belongs to another game")

    @staticmethod
    def _append_event_in_transaction(
        connection: sqlite3.Connection,
        *,
        game_id: UUID | None,
        event_type: str,
        payload: JsonObject,
        created_at: datetime,
    ) -> DirectoryEventRecord:
        """Append a lifecycle event inside the caller's transaction."""

        event_id = uuid4()
        payload_json = canonical_json(payload)
        payload_digest = canonical_digest(payload)
        cursor = connection.execute(
            """
            INSERT INTO directory_events(
                event_id, game_id, event_type, payload_json,
                payload_digest, created_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                str(event_id),
                str(game_id) if game_id else None,
                event_type,
                payload_json,
                payload_digest,
                datetime_to_text(created_at),
            ),
        ).lastrowid
        if cursor is None:
            raise RuntimeError("SQLite did not return a directory-event cursor")
        row = GameDirectoryRepository._required_row(
            connection,
            "SELECT * FROM directory_events WHERE cursor = ?",
            (cursor,),
            "directory event",
        )
        return _event_from_row(row)

    @staticmethod
    def _artifact_semantics(value: ArtifactCreate | ArtifactRecord) -> tuple[object, ...]:
        """Return immutable artifact fields used for idempotence checks."""

        return (
            value.game_id,
            value.artifact_kind,
            value.schema_version,
            value.media_type,
            value.uri,
            value.byte_size,
            value.content_digest,
            value.producer_kind,
            value.producer_version,
        )

    @staticmethod
    def _admission_semantics(
        value: RatingAdmissionCreate | RatingAdmissionRecord,
    ) -> tuple[object, ...]:
        """Return immutable rating-admission fields."""

        return (
            value.rating_run_id,
            value.game_id,
            value.summary_digest,
            value.admitted,
            value.exclusion_reason_code,
            canonical_json(value.exclusion_detail),
            value.treatment_id,
            value.configuration_id,
            value.weight,
        )

    @staticmethod
    def _estimate_semantics(
        value: RatingEstimateCreate | RatingEstimateRecord,
    ) -> tuple[object, ...]:
        """Return immutable rating-estimate fields."""

        return (
            value.rating_run_id,
            value.subject_id,
            value.estimate,
            value.uncertainty,
            value.games,
            value.wins,
            value.losses,
            value.draws,
            value.rank,
            canonical_json(value.diagnostics),
        )
