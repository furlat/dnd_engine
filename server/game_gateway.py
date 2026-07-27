"""Multi-game cold control plane and hot worker gateway.

The standalone :mod:`server.event_server` remains a complete database-free,
single-game server. This module is an additive host: SQLite is consulted only
during directory, creation, attachment, and archival operations. Runtime HTTP
and SSE traffic is authorized from memory and forwarded directly to one
isolated worker.
"""

from __future__ import annotations

import asyncio
import hmac
import json
import logging
import os
import secrets
import socket
import unicodedata
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import AsyncIterator, Callable, Iterable, TypeVar
from uuid import UUID, uuid4

import httpx
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from dnd.content_system.bootstrap import bootstrap_content_system
from dnd.content_system.pack_loader import LoadedContentSystem
from dnd.core.content.character_deployment import CharacterDeploymentSnapshot
from server.character_directory_contracts import (
    CharacterAdvancementResponse,
    CharacterBuildValidationRequest,
    CharacterBuildValidationResponse,
    CharacterDefinitionHistoryResponse,
    CharacterLevelUpRequest,
    CharacterLoadoutMutationRequest,
    CharacterRespecRequest,
    CharacterSnapshotResponse,
    CreateCharacterRequest,
)
from server.character_directory_service import (
    CharacterDirectoryBuildError,
    CharacterDirectoryOwnershipError,
    CharacterDirectoryService,
)
from server.character_directory_routes import create_character_directory_router
from server.character_deployment import build_character_deployment_snapshot
from server.character_settlement import (
    WorkerCharacterHoldingsEvidence,
    build_terminal_settlement_bundle,
)
from server.api_models import (
    GameCreationActivateRequest,
    GameCreationActivateResponse,
    GameCreationCatalogResponse,
    GameCreationComposedScenario,
    GameCreationPreflightRequest,
    CreateSessionResponse,
    GameCreationSideResult,
    GameCreationStartResponse,
    JoinGameResponse,
    SpellCatalogResponse,
    ServerCapabilitiesResponse,
)
from server.player_replication_contract import SubjectiveReplicationBootstrap
from server.directory_event_stream import (
    DirectoryEventStream,
    create_directory_event_stream_router,
)
from server.content_catalog import (
    ContentCatalogResponse,
    ContentManifestResponse,
    build_content_manifest,
    build_public_content_catalog,
    content_response_etag,
)
from server.event_contract import EVENT_CONTRACT_HASH
from server.game_directory.canonical import hash_capability
from server.game_directory.contracts import (
    AccessGrantCreate,
    AttachmentState,
    AttachmentCreate,
    CharacterDeploymentLeaseCreate,
    CharacterDefinitionRecord,
    CharacterRecord,
    ClientKind,
    DirectoryEventRecord,
    EntityAssignmentCreate,
    EntityAssignmentRecord,
    ExecutionKind,
    GameCreate,
    GameLifecycleState,
    GameRecord,
    GrantKind,
    MembershipCapabilities,
    MembershipCreate,
    MembershipRecord,
    MembershipRole,
    MembershipState,
    ObserverPolicy,
    PinnedCharacterDeploymentCreate,
    PrincipalCreate,
    PrincipalCredentialCreate,
    PrincipalKind,
    PrincipalRecord,
    ProducerKind,
    ProfileSettingsRecord,
    WorkerCreate,
    WorkerState,
    WorkerTerminalReadyManifestCreate,
    WorkerTerminalReadyManifestRecord,
    WorkerTransportKind,
)
from server.game_directory.errors import (
    CapabilityError,
    ConflictError,
    DirectoryError,
    NotFoundError,
)
from server.game_directory.repository import GameDirectoryRepository
from server.game_artifact_store import GameArtifactStore, ArtifactStoreError
from server.game_gateway_models import (
    AttachmentPolicy,
    AttachHostedGameRequest,
    AttachHostedGameResponse,
    CreateAgentGrantRequest,
    CreateAgentGrantResponse,
    CreateHostedGameRequest,
    CreateHostedGameResponse,
    GuestPrincipalRequest,
    GuestPrincipalResponse,
    HostedGameConnection,
    ObserveHostedGameRequest,
    ObserveHostedGameResponse,
    PlayerIdentityRequest,
    PlayerIdentityResponse,
    ReconnectHostedGameRequest,
    ReconnectHostedGameResponse,
    StopHostedGameRequest,
    StopHostedGameResponse,
)
from server.game_history import (
    GameHistoryQueryError,
    GameHistoryQueryService,
    create_game_history_router,
)
from server.game_history_contracts import GameHistoryListResponse
from dnd.scenarios.evaluation.compatibility import CompatibilityReport
from server.game_creation_catalog import (
    GameCreationCatalogError,
    build_game_creation_catalog,
    preflight_game_creation,
)
from server.hosted_worker import (
    CORE_HOSTED_WORKER_APPLICATION,
    HostedWorkerApplication,
    HostedWorkerError,
    HostedWorkerManager,
)
from server.game_summary_store import WorkerSummaryEvidence
from server.objective_replay import ObjectiveReplayBundle
from server.player_replay import (
    SubjectivePlayerReplayArchive,
    SubjectivePlayerReplayBundle,
)
from server.game_runtime_identity import ENGINE_VERSION, RULESET_VERSION
from server.terminal_evidence import (
    TerminalEvidenceError,
    store_terminal_artifacts,
    validate_stored_terminal_artifacts,
)
from server.worker_terminal_spool import (
    WorkerTerminalSpool,
    WorkerTerminalSpoolError,
    WorkerTerminalSpoolNotReady,
)
from server.runtime_authority import (
    RuntimeAuthorityCache,
    RuntimeScope,
    runtime_projection_headers,
)
from server.request_timing import RequestTimingMiddleware
from server.spell_catalog import build_spell_catalog
from server.worker_proxy import proxy_runtime_request


DEFAULT_RUNTIME_TTL_SECONDS = 60 * 60
TERMINAL_SUMMARY_READY_TIMEOUT_SECONDS = 5.0
TERMINAL_SUMMARY_RETRY_INTERVAL_SECONDS = 0.01
WorkerResponseT = TypeVar("WorkerResponseT", bound=BaseModel)
logger = logging.getLogger("dnd_game_gateway")


class GatewayError(RuntimeError):
    """Typed public gateway failure."""

    def __init__(self, status_code: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


class GameGatewayService:
    """Coordinate cold directory handshakes and isolated hot workers."""

    def __init__(
        self,
        repository: GameDirectoryRepository,
        worker_manager: HostedWorkerManager,
        authority_cache: RuntimeAuthorityCache,
        artifact_store: GameArtifactStore,
        *,
        capability_pepper: bytes,
        content_system: LoadedContentSystem | None = None,
        runtime_ttl_seconds: int = DEFAULT_RUNTIME_TTL_SECONDS,
    ) -> None:
        self.repository = repository
        self.worker_manager = worker_manager
        self.authority_cache = authority_cache
        self.artifact_store = artifact_store
        self.game_history = GameHistoryQueryService(
            repository,
            artifact_store,
        )
        self.capability_pepper = capability_pepper
        self.content_system = content_system or bootstrap_content_system()
        self.content_set_digest = self.content_system.content_set_digest
        self.character_directory = CharacterDirectoryService(
            repository,
            self.content_system,
        )
        if (
            self.content_set_digest
            != worker_manager.expected_content_set_digest
        ):
            raise ValueError(
                "Gateway and worker manager content identities differ",
            )
        self.runtime_ttl_seconds = runtime_ttl_seconds
        self._recover_worker_terminal_manifests()
        self._reconcile_orphaned_active_games()
        self.directory_stream = DirectoryEventStream(
            lambda since, limit: self.repository.list_directory_events(
                since_cursor=since,
                limit=limit,
            )
        )
        self._terminal_monitors: dict[UUID, asyncio.Task[None]] = {}
        self._terminal_persistence_locks: dict[UUID, asyncio.Lock] = {}
        self._publish_new_directory_events()

    def _recover_worker_terminal_manifests(self) -> None:
        """Adopt staged and worker-spooled terminal evidence before orphans."""

        for manifest in (
            self.repository.list_pending_worker_terminal_ready_manifests()
        ):
            try:
                self._adopt_staged_worker_terminal_manifest(manifest)
            except Exception:
                logger.exception(
                    "staged worker terminal manifest adoption failed for %s",
                    manifest.game_id,
                )
        for game in self.repository.list_games(
            lifecycle_state=GameLifecycleState.ACTIVE,
            limit=1_000,
        ):
            if game.lifecycle_state is GameLifecycleState.ENDED:
                continue
            try:
                self._stage_and_adopt_worker_terminal_spool(game)
            except WorkerTerminalSpoolNotReady:
                continue
            except Exception:
                logger.exception(
                    "worker terminal spool recovery failed for %s",
                    game.game_id,
                )

    def _stage_and_adopt_worker_terminal_spool(
        self,
        game: GameRecord,
    ) -> bool:
        """Import and adopt the exact ready file for one hosted game."""

        if game.worker_id is None or game.worker_generation is None:
            return False
        bundle = WorkerTerminalSpool(
            self.worker_manager.runtime_directory(game.game_id),
        ).read_ready(
            expected_game_id=game.game_id,
            expected_worker_instance_id=game.worker_id,
            expected_worker_generation=game.worker_generation,
        )
        replay_artifact, subjective_artifact = store_terminal_artifacts(
            artifact_store=self.artifact_store,
            game_id=game.game_id,
            evidence=bundle.summary,
            objective_replay=bundle.objective_replay,
            subjective_replay=bundle.subjective_replay,
            known_membership_ids=frozenset(
                membership.membership_id
                for membership in self.repository.list_memberships(
                    game.game_id,
                )
            ),
            producer_kind=ProducerKind.WORKER,
            producer_version=ENGINE_VERSION,
        )
        manifest = self.repository.stage_worker_terminal_ready_manifest(
            WorkerTerminalReadyManifestCreate(
                game_id=game.game_id,
                worker_id=game.worker_id,
                worker_generation=game.worker_generation,
                objective_artifact=replay_artifact,
                subjective_artifact=subjective_artifact,
                summary_evidence=bundle.summary.model_dump(mode="json"),
                settlement_evidence=(
                    bundle.holdings.model_dump(mode="json")
                    if bundle.holdings is not None
                    else None
                ),
                manifest_digest=bundle.manifest.manifest_digest,
                ready_at=bundle.manifest.ready_at,
            ),
        )
        self._adopt_staged_worker_terminal_manifest(manifest)
        return True

    def _adopt_staged_worker_terminal_manifest(
        self,
        manifest: WorkerTerminalReadyManifestRecord,
    ) -> None:
        """Integrity-check and atomically adopt one staged terminal manifest."""

        evidence = WorkerSummaryEvidence.model_validate(
            manifest.summary_evidence,
        )
        holdings_evidence = (
            WorkerCharacterHoldingsEvidence.model_validate(
                manifest.settlement_evidence,
            )
            if manifest.settlement_evidence is not None
            else None
        )
        validate_stored_terminal_artifacts(
            artifact_store=self.artifact_store,
            game_id=manifest.game_id,
            evidence=evidence,
            objective_artifact=manifest.objective_artifact,
            subjective_artifact=manifest.subjective_artifact,
            known_membership_ids=frozenset(
                membership.membership_id
                for membership in self.repository.list_memberships(
                    manifest.game_id,
                )
            ),
        )
        settlement_bundle = None
        lease_id = None
        if holdings_evidence is not None:
            leases = tuple(
                lease
                for lease in (
                    self.repository.list_character_deployment_leases(
                        game_id=manifest.game_id,
                        active_only=True,
                    )
                )
                if lease.character_id == holdings_evidence.character_id
            )
            if len(leases) != 1:
                raise ConflictError(
                    "Hosted terminal holdings evidence requires exactly one "
                    "matching active character lease",
                )
            lease = leases[0]
            deployments = tuple(
                deployment
                for deployment in (
                    self.repository.list_character_deployments(
                        holdings_evidence.character_id,
                    )
                )
                if (
                    deployment.game_id == manifest.game_id
                    and deployment.lease_id == lease.lease_id
                )
            )
            if len(deployments) != 1:
                raise ConflictError(
                    "Hosted terminal holdings evidence requires exactly one "
                    "matching pinned deployment",
                )
            settlement_bundle = build_terminal_settlement_bundle(
                holdings_evidence,
                deployments[0],
                settlement_namespace=(
                    "dnd-engine:hosted-character-settlement:v1"
                ),
            )
            lease_id = lease.lease_id
        self.repository.finalize_staged_worker_terminal_commit(
            manifest.objective_artifact,
            evidence.summary,
            subjective_artifact=manifest.subjective_artifact,
            summary_revision=1,
            source_event_digest=evidence.source_event_digest,
            source_combat_log_digest=(
                evidence.source_combat_log_digest
            ),
            manifest_digest=manifest.manifest_digest,
            summary_evidence=manifest.summary_evidence,
            settlement_evidence=manifest.settlement_evidence,
            settlement_bundle=settlement_bundle,
            lease_id=lease_id,
        )

    async def close(self) -> None:
        """Stop monitors and durably interrupt workers owned by this gateway."""
        for game_id in self.worker_manager.active_game_ids():
            lock = self._terminal_persistence_locks.setdefault(game_id, asyncio.Lock())
            async with lock:
                try:
                    async with self.worker_manager.client(game_id) as client:
                        await self._persist_worker_summary_if_ready_under_lock(
                            game_id,
                            client,
                        )
                except Exception:
                    logger.exception(
                        "terminal evidence reconciliation failed during shutdown for %s",
                        game_id,
                    )
                monitor = self._terminal_monitors.pop(game_id, None)
                if monitor is not None:
                    monitor.cancel()
                    await asyncio.gather(monitor, return_exceptions=True)
                await self.worker_manager.stop(game_id)
                self.authority_cache.revoke_game(game_id)
                game = self.repository.get_game(game_id)
                if game.worker_id is not None:
                    self.repository.update_worker(
                        game.worker_id,
                        state=WorkerState.STOPPED,
                        stopped_at=datetime.now(UTC),
                    )
                if game.lifecycle_state in {
                    GameLifecycleState.RESERVED,
                    GameLifecycleState.STARTING,
                    GameLifecycleState.ACTIVE,
                }:
                    self.repository.terminate_game_and_release_leases(
                        game_id,
                        expected_row_version=game.row_version,
                        lifecycle_state=GameLifecycleState.INTERRUPTED,
                        terminal_reason="gateway_shutdown",
                    )
        remaining_tasks = tuple(self._terminal_monitors.values())
        self._terminal_monitors.clear()
        for task in remaining_tasks:
            task.cancel()
        if remaining_tasks:
            await asyncio.gather(*remaining_tasks, return_exceptions=True)
        self._publish_new_directory_events()

    def _reconcile_orphaned_active_games(self) -> None:
        """Interrupt every orphaned nonterminal game after gateway restart."""

        for state in (
            GameLifecycleState.RESERVED,
            GameLifecycleState.STARTING,
            GameLifecycleState.ACTIVE,
        ):
            for game in self.repository.list_games(
                lifecycle_state=state,
                limit=1000,
            ):
                if self.worker_manager.placement(game.game_id) is not None:
                    continue
                if game.worker_id is not None:
                    self.repository.update_worker(
                        game.worker_id,
                        state=WorkerState.LOST,
                        stopped_at=datetime.now(UTC),
                        failure_code="gateway_restart",
                        failure_detail={"game_id": str(game.game_id)},
                    )
                self.repository.terminate_game_and_release_leases(
                    game.game_id,
                    expected_row_version=game.row_version,
                    lifecycle_state=GameLifecycleState.INTERRUPTED,
                    terminal_reason="gateway_restart",
                )

    def create_guest_principal(self, request: GuestPrincipalRequest) -> GuestPrincipalResponse:
        """Create one durable local identity and return its secret once."""
        capability = secrets.token_urlsafe(32)
        principal = self.repository.create_principal(
            PrincipalCreate(
                principal_kind=PrincipalKind.HUMAN,
                display_name=request.display_name,
                credential_hash=hash_capability(capability, self.capability_pepper),
            )
        )
        self._create_default_profile_settings(principal.principal_id)
        self._publish_new_directory_events()
        return GuestPrincipalResponse(
            principal=principal,
            principal_capability=capability,
        )

    def identify_player(self, request: PlayerIdentityRequest) -> PlayerIdentityResponse:
        """Resolve one local-trust player name and issue this client a credential."""

        display_name = " ".join(request.display_name.split())
        if not display_name:
            raise GatewayError(400, "player_name_empty", "Player name cannot be blank")
        identity_key = unicodedata.normalize("NFKC", display_name).casefold()
        principal, _ = self.repository.resolve_player_identity(
            identity_key,
            PrincipalCreate(
                principal_kind=PrincipalKind.HUMAN,
                display_name=display_name,
                metadata={"authentication_kind": "name_only_local"},
            ),
        )
        capability = secrets.token_urlsafe(32)
        credential = self.repository.issue_principal_credential(
            PrincipalCredentialCreate(
                principal_id=principal.principal_id,
                client_instance_id=request.client_instance_id,
                secret_hash=hash_capability(capability, self.capability_pepper),
            )
        )
        self._ensure_profile_settings(principal.principal_id)
        self._publish_new_directory_events()
        return PlayerIdentityResponse(
            principal=principal,
            credential_id=credential.credential_id,
            principal_capability=capability,
        )

    def _create_default_profile_settings(
        self,
        principal_id: UUID,
    ) -> ProfileSettingsRecord:
        return self.character_directory.ensure_profile_settings(principal_id)

    def _ensure_profile_settings(
        self,
        principal_id: UUID,
    ) -> ProfileSettingsRecord:
        return self.character_directory.ensure_profile_settings(principal_id)

    def create_character(
        self,
        principal_id: UUID,
        principal_capability: str,
        request: CreateCharacterRequest,
    ) -> CharacterSnapshotResponse:
        """Create one normalized schema-2 persistent character."""

        principal = self._authenticate_principal(
            principal_id,
            principal_capability,
        )
        character = self.character_directory.create_character(
            principal.principal_id,
            request,
        )
        self._publish_new_directory_events()
        return character

    def get_character_definition(
        self,
        principal_id: UUID,
        principal_capability: str,
        character_id: UUID,
    ) -> CharacterDefinitionRecord:
        """Return the authenticated owner's exact current structural revision."""

        principal = self._authenticate_principal(
            principal_id,
            principal_capability,
        )
        return self.character_directory.get_character_snapshot(
            principal.principal_id,
            character_id,
        ).definition

    def validate_character_build(
        self,
        principal_id: UUID,
        principal_capability: str,
        request: CharacterBuildValidationRequest,
    ) -> CharacterBuildValidationResponse:
        """Validate a creation build under the authenticated profile policy."""

        principal = self._authenticate_principal(
            principal_id,
            principal_capability,
        )
        return self.character_directory.validate_new_character(
            principal.principal_id,
            request,
        )

    def get_character_snapshot(
        self,
        principal_id: UUID,
        principal_capability: str,
        character_id: UUID,
    ) -> CharacterSnapshotResponse:
        principal = self._authenticate_principal(
            principal_id,
            principal_capability,
        )
        return self.character_directory.get_character_snapshot(
            principal.principal_id,
            character_id,
        )

    def get_character_definition_history(
        self,
        principal_id: UUID,
        principal_capability: str,
        character_id: UUID,
    ) -> CharacterDefinitionHistoryResponse:
        principal = self._authenticate_principal(
            principal_id,
            principal_capability,
        )
        return self.character_directory.get_definition_history(
            principal.principal_id,
            character_id,
        )

    def get_character_advancement(
        self,
        principal_id: UUID,
        principal_capability: str,
        character_id: UUID,
    ) -> CharacterAdvancementResponse:
        principal = self._authenticate_principal(
            principal_id,
            principal_capability,
        )
        return self.character_directory.get_advancement(
            principal.principal_id,
            character_id,
        )

    def validate_character_level_up(
        self,
        principal_id: UUID,
        principal_capability: str,
        character_id: UUID,
        request: CharacterLevelUpRequest,
    ) -> CharacterBuildValidationResponse:
        principal = self._authenticate_principal(
            principal_id,
            principal_capability,
        )
        return self.character_directory.validate_level_up(
            principal.principal_id,
            character_id,
            request,
        )

    def level_up_character(
        self,
        principal_id: UUID,
        principal_capability: str,
        character_id: UUID,
        request: CharacterLevelUpRequest,
    ) -> CharacterSnapshotResponse:
        principal = self._authenticate_principal(
            principal_id,
            principal_capability,
        )
        result = self.character_directory.level_up(
            principal.principal_id,
            character_id,
            request,
        )
        self._publish_new_directory_events()
        return result

    def validate_character_respec(
        self,
        principal_id: UUID,
        principal_capability: str,
        character_id: UUID,
        request: CharacterRespecRequest,
    ) -> CharacterBuildValidationResponse:
        principal = self._authenticate_principal(
            principal_id,
            principal_capability,
        )
        return self.character_directory.validate_respec(
            principal.principal_id,
            character_id,
            request,
        )

    def respec_character(
        self,
        principal_id: UUID,
        principal_capability: str,
        character_id: UUID,
        request: CharacterRespecRequest,
    ) -> CharacterSnapshotResponse:
        principal = self._authenticate_principal(
            principal_id,
            principal_capability,
        )
        result = self.character_directory.respec(
            principal.principal_id,
            character_id,
            request,
        )
        self._publish_new_directory_events()
        return result

    def validate_character_loadout(
        self,
        principal_id: UUID,
        principal_capability: str,
        character_id: UUID,
        request: CharacterLoadoutMutationRequest,
    ) -> CharacterBuildValidationResponse:
        principal = self._authenticate_principal(
            principal_id,
            principal_capability,
        )
        return self.character_directory.validate_loadout(
            principal.principal_id,
            character_id,
            request,
        )

    def update_character_loadout(
        self,
        principal_id: UUID,
        principal_capability: str,
        character_id: UUID,
        request: CharacterLoadoutMutationRequest,
    ) -> CharacterSnapshotResponse:
        principal = self._authenticate_principal(
            principal_id,
            principal_capability,
        )
        result = self.character_directory.update_loadout(
            principal.principal_id,
            character_id,
            request,
        )
        self._publish_new_directory_events()
        return result

    async def create_hosted_game(
        self,
        request: CreateHostedGameRequest,
        *,
        public_gateway_base_url: str,
    ) -> CreateHostedGameResponse:
        """Create one worker, game, owner membership, and hot attachment."""
        principal = self._authenticate_principal(
            request.principal_id,
            request.principal_capability,
        )
        character: CharacterRecord | None = None
        character_deployment = None
        if request.creation.character_id is not None:
            character = self.repository.get_character(
                request.creation.character_id,
            )
            if character.owner_principal_id != principal.principal_id:
                raise GatewayError(403, "character_not_owned", "Character belongs to another player")
            if character.status.value != "active":
                raise GatewayError(409, "character_not_active", "Character is not active")
            if request.owner_side != "side_a" or not isinstance(
                request.creation.scenario,
                GameCreationComposedScenario,
            ):
                raise GatewayError(
                    400,
                    "character_seat_invalid",
                    "Persistent characters can currently enter only the composed hero seat",
                )
            if (
                character.current_definition_revision is None
                or character.revision_state.value != "canonical"
            ):
                raise GatewayError(
                    409,
                    "character_revisions_unavailable",
                    "Persistent character has not been migrated to exact revisions",
                )
            character_deployment = build_character_deployment_snapshot(
                self.character_directory,
                principal.principal_id,
                character.character_id,
            )
        selected_side_request = (
            request.creation.side_a
            if request.owner_side == "side_a"
            else request.creation.side_b
            if request.owner_side == "side_b"
            else None
        )
        if selected_side_request is not None and selected_side_request.controller == "ai":
            raise GatewayError(
                400,
                "owner_side_is_automatic",
                "The owner can attach only to a human or Codex side",
            )
        hosted_game_id = uuid4()
        runtime_base_url = (
            f"{public_gateway_base_url.rstrip('/')}/games/{hosted_game_id}/runtime"
        )
        game: GameRecord | None = None
        worker_id: UUID | None = None
        try:
            placement = await self.worker_manager.start(
                hosted_game_id,
                public_game_base_url=runtime_base_url,
                character_deployment=character_deployment,
            )
            async with self.worker_manager.client(hosted_game_id, timeout=60.0) as client:
                worker_response = await client.post(
                    "/game-creation/start",
                    json=request.creation.model_dump(mode="json"),
                )
            creation = self._validate_worker_response(
                worker_response,
                GameCreationStartResponse,
                "game_creation_failed",
            )
            worker = self.repository.create_worker(
                WorkerCreate(
                    worker_id=placement.worker_instance_id,
                    state=WorkerState.ACTIVE,
                    pid=placement.process_id,
                    process_group_id=placement.process_group_id,
                    host_id=socket.gethostname(),
                    transport_kind=WorkerTransportKind.UNIX_SOCKET,
                    private_locator=placement.socket_path,
                    protocol_hash=EVENT_CONTRACT_HASH,
                    engine_version=ENGINE_VERSION,
                )
            )
            worker_id = worker.worker_id
            game = self.repository.create_game(
                GameCreate(
                    game_id=hosted_game_id,
                    engine_game_id=UUID(creation.game_id),
                    worker_id=worker.worker_id,
                    worker_generation=worker.worker_generation,
                    created_by_principal_id=principal.principal_id,
                    lifecycle_state=GameLifecycleState.STARTING,
                    visibility_policy=request.visibility_policy,
                    observer_policy=request.observer_policy,
                    execution_kind=ExecutionKind.HOSTED,
                    scenario_kind=creation.scenario_kind,
                    scenario_id=_scenario_id(request),
                    display_name=request.display_name,
                    creation_manifest={
                        "request": request.creation.model_dump(mode="json"),
                        "response": creation.model_dump(mode="json"),
                        "content_set_digest": self.content_set_digest,
                    },
                    ruleset_version=RULESET_VERSION,
                    engine_version=ENGINE_VERSION,
                    content_digest=self.content_set_digest,
                )
            )
            side = _selected_side(creation, request.owner_side)
            membership = self._create_owner_membership(
                game,
                principal,
                request.owner_side,
                side,
            )
            runtime_session_id, controlled_entities = await self._create_owner_runtime_session(
                game,
                membership,
                principal,
                request.owner_side,
                side,
            )
            if side is not None:
                self._persist_entity_assignments(game, membership, side)
            if character is not None:
                assert character_deployment is not None
                if side is None or len(side.entity_assignments) != 1:
                    raise GatewayError(
                        409,
                        "character_deployment_ambiguous",
                        "Persistent character deployment requires exactly one hero entity",
                    )
                lease = self.repository.acquire_character_deployment_lease(
                    CharacterDeploymentLeaseCreate(
                        character_id=character.character_id,
                        game_id=game.game_id,
                        membership_id=membership.membership_id,
                    ),
                )
                current_character = self.repository.get_character(
                    character.character_id,
                )
                if not _character_matches_deployment_snapshot(
                    current_character,
                    character_deployment,
                ):
                    raise GatewayError(
                        409,
                        "character_heads_changed_during_deployment",
                        (
                            "Character revisions changed while the worker was "
                            "being prepared; retry game creation"
                        ),
                    )
                self.repository.deploy_character_pinned(
                    PinnedCharacterDeploymentCreate(
                        game_id=game.game_id,
                        membership_id=membership.membership_id,
                        character_id=character.character_id,
                        entity_uuid=UUID(side.entity_assignments[0].entity_uuid),
                        lease_id=lease.lease_id,
                    )
                )
            reconnect = self.repository.issue_access_grant(
                AccessGrantCreate(
                    game_id=game.game_id,
                    membership_id=membership.membership_id,
                    issued_to_principal_id=principal.principal_id,
                    grant_kind=GrantKind.RECONNECT,
                    scope={"membership_id": str(membership.membership_id)},
                    issued_by_principal_id=principal.principal_id,
                )
            )
            connection = self._open_hot_connection(
                game=game,
                membership=membership,
                runtime_session_id=runtime_session_id,
                controlled_entity_uuids=controlled_entities,
                observer_entity_uuids=self._observer_entities_for_membership(
                    game,
                    membership,
                    controlled_entities,
                ),
                takeover_claim_uuids=_side_takeover_claims(side),
                client_kind=request.client_kind,
                client_instance_id=request.client_instance_id,
                runtime_base_url=runtime_base_url,
            )
            await self._bootstrap_and_activate_created_game(
                game,
                connection,
            )
            game = self.repository.transition_game(
                game.game_id,
                expected_row_version=game.row_version,
                lifecycle_state=GameLifecycleState.ACTIVE,
            )
        except BaseException as exc:
            await self.worker_manager.stop(hosted_game_id)
            self.authority_cache.revoke_game(hosted_game_id)
            if worker_id is not None:
                self.repository.update_worker(
                    worker_id,
                    state=WorkerState.FAILED,
                    stopped_at=datetime.now(UTC),
                    failure_code="provisioning_failed",
                    failure_detail={"error_type": type(exc).__name__},
                )
            if game is not None:
                latest_game = self.repository.get_game(game.game_id)
                self.repository.terminate_game_and_release_leases(
                    latest_game.game_id,
                    expected_row_version=latest_game.row_version,
                    lifecycle_state=GameLifecycleState.FAILED,
                    terminal_reason="provisioning_failed",
                )
            self._publish_new_directory_events()
            raise

        self._publish_new_directory_events()
        if await self._reconcile_worker_summary_if_ready(game.game_id):
            game = self.repository.get_game(game.game_id)
        else:
            self._start_terminal_monitor(game.game_id)
        return CreateHostedGameResponse(
            game=game,
            creation=creation,
            connection=connection,
            reconnect_grant_id=reconnect.grant.grant_id,
            reconnect_capability=reconnect.capability,
        )

    async def attach_existing_game(
        self,
        game_id: UUID,
        request: AttachHostedGameRequest,
        *,
        public_gateway_base_url: str,
    ) -> AttachHostedGameResponse:
        """Redeem a reconnect grant and mint fresh hot authority."""
        grant = self.repository.verify_access_grant(
            request.grant_id,
            request.capability,
            consume=False,
        )
        if grant.game_id != game_id or grant.membership_id is None:
            raise GatewayError(403, "grant_scope_mismatch", "Grant belongs to another game")
        if grant.grant_kind not in {
            GrantKind.RECONNECT,
            GrantKind.INVITE,
            GrantKind.OBSERVE,
            GrantKind.AGENT_ATTACH,
        }:
            raise GatewayError(403, "grant_kind_rejected", "Grant cannot open a runtime attachment")
        game = self.repository.get_game(game_id)
        self._require_live_game(game)
        membership = self.repository.get_membership(grant.membership_id)
        try:
            previous_runtime_session_id = self.repository.get_latest_attachment_for_membership(
                membership.membership_id
            ).runtime_session_id
        except NotFoundError:
            scoped_session_id = grant.scope.get("runtime_session_id")
            if not isinstance(scoped_session_id, str):
                raise GatewayError(
                    409,
                    "attachment_has_no_runtime_session",
                    "Grant cannot identify a worker session",
                )
            previous_runtime_session_id = UUID(scoped_session_id)
        controlled = tuple(
            assignment.entity_uuid
            for assignment in self.repository.list_entity_assignments(game_id)
            if assignment.membership_id == membership.membership_id
        )
        runtime_base_url = (
            f"{public_gateway_base_url.rstrip('/')}/games/{game_id}/runtime"
        )
        await self._require_worker_session(game_id, previous_runtime_session_id)
        connection = self._open_hot_connection(
            game=game,
            membership=membership,
            runtime_session_id=previous_runtime_session_id,
            controlled_entity_uuids=controlled,
            observer_entity_uuids=self._observer_entities_for_membership(
                game,
                membership,
                controlled,
            ),
            takeover_claim_uuids=self._takeover_claims_for_membership(game, membership),
            client_kind=request.client_kind,
            client_instance_id=request.client_instance_id,
            runtime_base_url=runtime_base_url,
        )
        self._publish_new_directory_events()
        return AttachHostedGameResponse(game=game, connection=connection)

    async def reconnect_player(
        self,
        game_id: UUID,
        request: ReconnectHostedGameRequest,
        *,
        public_gateway_base_url: str,
    ) -> ReconnectHostedGameResponse:
        """Reconnect an identity-owned seat with explicit attachment semantics."""

        principal = self._authenticate_principal(
            request.principal_id,
            request.principal_capability,
        )
        game = self.repository.get_game(game_id)
        self._require_live_game(game)
        membership = self.repository.get_membership(request.membership_id)
        if membership.game_id != game_id or membership.principal_id != principal.principal_id:
            raise GatewayError(403, "membership_not_owned", "Player does not own this game seat")
        if (
            membership.membership_state
            not in {MembershipState.ACTIVE, MembershipState.DISCONNECTED}
            or not membership.capabilities.may_connect
        ):
            raise GatewayError(409, "membership_not_connectable", "Game seat cannot reconnect")

        previous = self.repository.get_latest_attachment_for_membership(
            membership.membership_id
        )
        await self._require_worker_session(game_id, previous.runtime_session_id)
        replaced: list[UUID] = []
        if request.attachment_policy is AttachmentPolicy.REPLACE_EXISTING:
            connected = self.repository.list_attachments_for_membership(
                membership.membership_id,
                connected_only=True,
            )
            replaced = [attachment.attachment_id for attachment in connected]
            for attachment in connected:
                self.repository.close_attachment(
                    attachment.attachment_id,
                    state=AttachmentState.REVOKED,
                    reason="replaced_by_new_attachment",
                )
            self.authority_cache.revoke_membership(game_id, membership.membership_id)

        controlled = tuple(
            assignment.entity_uuid
            for assignment in self.repository.list_entity_assignments(game_id)
            if assignment.membership_id == membership.membership_id
        )
        runtime_base_url = (
            f"{public_gateway_base_url.rstrip('/')}/games/{game_id}/runtime"
        )
        connection = self._open_hot_connection(
            game=game,
            membership=membership,
            runtime_session_id=previous.runtime_session_id,
            controlled_entity_uuids=controlled,
            observer_entity_uuids=self._observer_entities_for_membership(
                game,
                membership,
                controlled,
            ),
            takeover_claim_uuids=self._takeover_claims_for_membership(game, membership),
            client_kind=request.client_kind,
            client_instance_id=request.client_instance_id,
            runtime_base_url=runtime_base_url,
        )
        self._publish_new_directory_events()
        return ReconnectHostedGameResponse(
            game=game,
            connection=connection,
            replaced_attachment_ids=replaced,
        )

    def create_remote_agent_grant(
        self,
        game_id: UUID,
        request: CreateAgentGrantRequest,
    ) -> CreateAgentGrantResponse:
        """Bind a remote agent identity to an already configured external side."""
        self._authenticate_principal(request.principal_id, request.principal_capability)
        agent_principal = self.repository.get_principal(request.agent_principal_id)
        game = self.repository.get_game(game_id)
        self._require_live_game(game)
        if not any(
            membership.principal_id == request.principal_id
            and membership.membership_state is MembershipState.ACTIVE
            and membership.capabilities.may_manage_members
            for membership in self.repository.list_memberships(game_id)
        ):
            raise GatewayError(403, "member_management_denied", "Principal may not attach agents")

        creation_payload = game.creation_manifest.get("response")
        if not isinstance(creation_payload, dict):
            raise GatewayError(500, "creation_manifest_invalid", "Game has no resolved creation response")
        creation = GameCreationStartResponse.model_validate(creation_payload)
        side = creation.side_a if request.side_id == "side_a" else creation.side_b
        if (
            side.controller != "codex"
            or side.codex_session_id is None
            or side.takeover_claim_id is None
        ):
            raise GatewayError(
                409,
                "side_not_external",
                "Remote agents may attach only to a side configured for Codex/external control",
            )
        if any(
            assignment.side_id == request.side_id
            for assignment in self.repository.list_entity_assignments(game_id)
        ):
            raise GatewayError(409, "side_already_assigned", "The requested side already has directory authority")

        membership: MembershipRecord | None = None
        assignments: tuple[EntityAssignmentRecord, ...] = ()
        try:
            membership = self.repository.create_membership(
                MembershipCreate(
                    game_id=game_id,
                    principal_id=agent_principal.principal_id,
                    role=MembershipRole.AGENT,
                    side_id=request.side_id,
                    controller_kind="remote_agent",
                    membership_state=MembershipState.ACTIVE,
                    capabilities=_agent_capabilities(),
                )
            )
            assignments = self._persist_entity_assignments(game, membership, side)
            runtime_session_id = UUID(side.codex_session_id)
            controlled = [
                UUID(assignment.entity_uuid)
                for assignment in side.entity_assignments
            ]
            issued = self.repository.issue_access_grant(
                AccessGrantCreate(
                    game_id=game_id,
                    membership_id=membership.membership_id,
                    issued_to_principal_id=agent_principal.principal_id,
                    grant_kind=GrantKind.AGENT_ATTACH,
                    scope={
                        "membership_id": str(membership.membership_id),
                        "runtime_session_id": str(runtime_session_id),
                        "side_id": request.side_id,
                        "takeover_claim_id": side.takeover_claim_id,
                    },
                    issued_by_principal_id=request.principal_id,
                )
            )
        except BaseException:
            for assignment in assignments:
                self.repository.release_entity(assignment.assignment_id)
            if membership is not None:
                self.repository.update_membership_authority(
                    membership.membership_id,
                    expected_authority_epoch=membership.authority_epoch,
                    membership_state=MembershipState.REVOKED,
                    capabilities=MembershipCapabilities(),
                )
            self._publish_new_directory_events()
            raise
        self._publish_new_directory_events()
        return CreateAgentGrantResponse(
            game=game,
            membership=membership,
            runtime_session_id=runtime_session_id,
            controlled_entity_uuids=controlled,
            takeover_claim_id=UUID(side.takeover_claim_id),
            grant_id=issued.grant.grant_id,
            grant_capability=issued.capability,
        )

    async def observe_game(
        self,
        game_id: UUID,
        request: ObserveHostedGameRequest,
        *,
        public_gateway_base_url: str,
    ) -> ObserveHostedGameResponse:
        """Create a policy-authorized observer membership and attachment."""
        principal = self._authenticate_principal(
            request.principal_id,
            request.principal_capability,
        )
        game = self.repository.get_game(game_id)
        self._require_live_game(game)
        if game.observer_policy is not ObserverPolicy.PUBLIC:
            raise GatewayError(403, "observers_not_public", "This game does not admit public observers")
        membership = self.repository.create_membership(
            MembershipCreate(
                game_id=game_id,
                principal_id=principal.principal_id,
                role=MembershipRole.OBSERVER,
                membership_state=MembershipState.ACTIVE,
                capabilities=_observer_capabilities(),
            )
        )
        observer_entities = self._observer_entities_for_membership(
            game,
            membership,
            (),
        )
        runtime_session_id = await self._create_and_join_session(
            game_id,
            player_type="observer",
            name=principal.display_name,
            entity_uuids=(),
            observer_entity_uuids=observer_entities,
            active_observer_uuid=min(observer_entities, key=str),
        )
        reconnect = self.repository.issue_access_grant(
            AccessGrantCreate(
                game_id=game_id,
                membership_id=membership.membership_id,
                issued_to_principal_id=principal.principal_id,
                grant_kind=GrantKind.RECONNECT,
                scope={"membership_id": str(membership.membership_id)},
                issued_by_principal_id=game.created_by_principal_id,
            )
        )
        runtime_base_url = (
            f"{public_gateway_base_url.rstrip('/')}/games/{game_id}/runtime"
        )
        connection = self._open_hot_connection(
            game=game,
            membership=membership,
            runtime_session_id=runtime_session_id,
            controlled_entity_uuids=(),
            observer_entity_uuids=observer_entities,
            takeover_claim_uuids=(),
            client_kind=request.client_kind,
            client_instance_id=request.client_instance_id,
            runtime_base_url=runtime_base_url,
        )
        self._publish_new_directory_events()
        return ObserveHostedGameResponse(
            game=game,
            connection=connection,
            reconnect_grant_id=reconnect.grant.grant_id,
            reconnect_capability=reconnect.capability,
        )

    async def stop_hosted_game(
        self,
        game_id: UUID,
        request: StopHostedGameRequest,
    ) -> StopHostedGameResponse:
        """Stop one worker after a cold administrative authorization check."""
        self._authenticate_principal(request.principal_id, request.principal_capability)
        game = self.repository.get_game(game_id)
        memberships = self.repository.list_memberships(game_id)
        authorized = any(
            membership.principal_id == request.principal_id
            and membership.membership_state is MembershipState.ACTIVE
            and membership.capabilities.may_manage_game
            for membership in memberships
        )
        if not authorized:
            raise GatewayError(403, "game_management_denied", "Principal may not stop this game")
        lock = self._terminal_persistence_locks.setdefault(game_id, asyncio.Lock())
        async with lock:
            return await self._stop_hosted_game_under_lock(game_id, game)

    async def _stop_hosted_game_under_lock(
        self,
        game_id: UUID,
        game: GameRecord,
    ) -> StopHostedGameResponse:
        """Reconcile terminal evidence and stop one worker under its game lock."""
        if game_id in self.worker_manager.active_game_ids():
            async with self.worker_manager.client(game_id) as client:
                await self._persist_worker_summary_if_ready_under_lock(
                    game_id,
                    client,
                )
        monitor = self._terminal_monitors.pop(game_id, None)
        if monitor is not None:
            monitor.cancel()
            await asyncio.gather(monitor, return_exceptions=True)
        stopped = await self.worker_manager.stop(game_id)
        self.authority_cache.revoke_game(game_id)
        game = self.repository.get_game(game_id)
        if game.worker_id is not None:
            self.repository.update_worker(
                game.worker_id,
                state=WorkerState.STOPPED,
                stopped_at=datetime.now(UTC),
            )
        if game.lifecycle_state not in {
            GameLifecycleState.ENDED,
            GameLifecycleState.FAILED,
            GameLifecycleState.INTERRUPTED,
            GameLifecycleState.ARCHIVED,
        }:
            game = self.repository.terminate_game_and_release_leases(
                game_id,
                expected_row_version=game.row_version,
                lifecycle_state=GameLifecycleState.INTERRUPTED,
                terminal_reason="administrative_stop",
            )
        self._publish_new_directory_events()
        return StopHostedGameResponse(game=game, stopped=stopped is not None)

    def list_visible_games(
        self,
        *,
        principal_id: UUID | None,
        principal_capability: str | None,
    ) -> GameHistoryListResponse:
        """List public games plus private games belonging to an authenticated principal."""
        visible_principal: PrincipalRecord | None = None
        if principal_id is not None or principal_capability is not None:
            if principal_id is None or principal_capability is None:
                raise GatewayError(400, "incomplete_principal_auth", "Both principal fields are required")
            visible_principal = self._authenticate_principal(principal_id, principal_capability)
        return self.game_history.list_visible_games(
            (
                visible_principal.principal_id
                if visible_principal is not None
                else None
            ),
        )

    def require_visible_game(
        self,
        game_id: UUID,
        *,
        principal_id: UUID | None,
        principal_capability: str | None,
    ) -> GameRecord:
        """Return a game only when directory visibility permits discovery."""
        resolved_principal_id: UUID | None = None
        if principal_id is None or principal_capability is None:
            if principal_id is not None or principal_capability is not None:
                raise GatewayError(
                    400,
                    "incomplete_principal_auth",
                    "Both principal fields are required",
                )
        else:
            resolved_principal_id = self._authenticate_principal(
                principal_id,
                principal_capability,
            ).principal_id
        try:
            return self.game_history.require_visible_game(
                game_id,
                resolved_principal_id,
            )
        except GameHistoryQueryError as exc:
            raise GatewayError(
                exc.status_code,
                exc.code,
                exc.message,
            ) from exc

    def get_objective_replay(
        self,
        game_id: UUID,
        *,
        principal_id: UUID,
        principal_capability: str,
    ) -> ObjectiveReplayBundle:
        """Read one ended replay under its explicit cold-evidence capability."""
        principal = self._authenticate_principal(
            principal_id,
            principal_capability,
        )
        try:
            return self.game_history.get_objective_replay(
                game_id,
                principal.principal_id,
            )
        except GameHistoryQueryError as exc:
            raise GatewayError(
                exc.status_code,
                exc.code,
                exc.message,
            ) from exc

    def get_subjective_replay(
        self,
        game_id: UUID,
        membership_id: UUID,
        *,
        principal_id: UUID,
        principal_capability: str,
    ) -> SubjectivePlayerReplayBundle:
        """Return only the ended canonical replay owned by one exact membership."""

        principal = self._authenticate_principal(
            principal_id,
            principal_capability,
        )
        try:
            return self.game_history.get_subjective_replay(
                game_id,
                membership_id,
                principal.principal_id,
            )
        except GameHistoryQueryError as exc:
            raise GatewayError(
                exc.status_code,
                exc.code,
                exc.message,
            ) from exc

    def _read_subjective_replay_archive(
        self,
        game_id: UUID,
    ) -> SubjectivePlayerReplayArchive:
        """Read and authenticate one aggregate archive without exposing it publicly."""
        try:
            return self.game_history.read_subjective_archive(game_id)
        except GameHistoryQueryError as exc:
            raise GatewayError(
                exc.status_code,
                exc.code,
                exc.message,
            ) from exc

    def directory_event_filter(
        self,
        *,
        principal_id: UUID | None,
        principal_capability: str | None,
    ) -> Callable[[DirectoryEventRecord], bool]:
        """Build one authenticated visibility predicate for directory events."""
        visible_principal: PrincipalRecord | None = None
        if principal_id is not None or principal_capability is not None:
            if principal_id is None or principal_capability is None:
                raise GatewayError(
                    400,
                    "incomplete_principal_auth",
                    "Both principal fields are required",
                )
            visible_principal = self._authenticate_principal(
                principal_id,
                principal_capability,
            )

        return self.game_history.directory_event_filter(
            None if visible_principal is None else visible_principal.principal_id,
        )

    def _authenticate_principal(self, principal_id: UUID, capability: str) -> PrincipalRecord:
        principal = self.repository.get_principal(principal_id)
        if principal.disabled_at is not None:
            raise GatewayError(403, "principal_disabled", "Principal cannot authenticate")
        supplied = hash_capability(capability, self.capability_pepper)
        if principal.credential_hash is not None and hmac.compare_digest(
            principal.credential_hash,
            supplied,
        ):
            return principal
        try:
            self.repository.authenticate_principal_credential(principal_id, capability)
        except NotFoundError as exc:
            raise GatewayError(
                403,
                "principal_capability_invalid",
                "Principal capability is invalid",
            ) from exc
        return principal

    def _create_owner_membership(
        self,
        game: GameRecord,
        principal: PrincipalRecord,
        owner_side: str,
        side: GameCreationSideResult | None,
    ) -> MembershipRecord:
        controller_kind = side.controller if side is not None else None
        return self.repository.create_membership(
            MembershipCreate(
                game_id=game.game_id,
                principal_id=principal.principal_id,
                role=MembershipRole.OWNER,
                side_id=side.side_id if side is not None else None,
                controller_kind=controller_kind,
                membership_state=MembershipState.ACTIVE,
                capabilities=_owner_capabilities(owner_side != "observer", controller_kind == "codex"),
            )
        )

    async def _create_owner_runtime_session(
        self,
        game: GameRecord,
        membership: MembershipRecord,
        principal: PrincipalRecord,
        owner_side: str,
        side: GameCreationSideResult | None,
    ) -> tuple[UUID, tuple[UUID, ...]]:
        if side is None:
            observers = self._observer_entities_for_membership(game, membership, ())
            session_id = await self._create_and_join_session(
                game.game_id,
                player_type="observer",
                name=principal.display_name,
                entity_uuids=(),
                observer_entity_uuids=observers,
                active_observer_uuid=min(observers, key=str),
            )
            return session_id, ()
        controlled = tuple(
            UUID(assignment.entity_uuid)
            for assignment in side.entity_assignments
        )
        if side.controller == "codex":
            if side.codex_session_id is None:
                raise GatewayError(502, "codex_session_missing", "Worker did not return a Codex session")
            return UUID(side.codex_session_id), controlled
        session_id = await self._create_and_join_session(
            game.game_id,
            player_type="human",
            name=principal.display_name,
            entity_uuids=controlled,
        )
        return session_id, controlled

    async def _create_and_join_session(
        self,
        game_id: UUID,
        *,
        player_type: str,
        name: str,
        entity_uuids: Iterable[UUID],
        observer_entity_uuids: Iterable[UUID] = (),
        active_observer_uuid: UUID | None = None,
    ) -> UUID:
        async with self.worker_manager.client(game_id) as client:
            created_response = await client.post(
                "/session/create",
                json={"player_type": player_type, "name": name},
            )
            created = self._validate_worker_response(
                created_response,
                CreateSessionResponse,
                "session_creation_failed",
            )
            join_payload: dict[str, object] = {
                "session_id": created.session_id,
                "entity_uuids": [str(entity_uuid) for entity_uuid in entity_uuids],
            }
            if player_type == "observer":
                join_payload["observer_entity_uuids"] = [
                    str(entity_uuid) for entity_uuid in observer_entity_uuids
                ]
                join_payload["active_observer_uuid"] = (
                    str(active_observer_uuid) if active_observer_uuid is not None else None
                )
            joined_response = await client.post(
                "/game/join",
                json=join_payload,
            )
            self._validate_worker_response(
                joined_response,
                JoinGameResponse,
                "session_join_failed",
            )
        return UUID(created.session_id)

    async def _bootstrap_and_activate_created_game(
        self,
        game: GameRecord,
        connection: HostedGameConnection,
    ) -> GameCreationActivateResponse:
        """Open the owner's exact reducer seed before releasing gameplay."""
        authority = self.authority_cache.validate(
            connection.runtime_token,
            hosted_game_id=game.game_id,
            required_scope=RuntimeScope.SUBJECTIVE_OBSERVE,
        )
        headers = runtime_projection_headers(authority)
        async with self.worker_manager.client(game.game_id) as client:
            bootstrap_response = await client.get(
                "/replication/bootstrap",
                params={"session_id": str(connection.runtime_session_id)},
                headers=headers,
            )
            bootstrap = self._validate_worker_response(
                bootstrap_response,
                SubjectiveReplicationBootstrap,
                "replication_bootstrap_failed",
            )
            activation = GameCreationActivateRequest(
                session_id=str(connection.runtime_session_id),
                expected_source_stream_id=bootstrap.protocol.source_stream_id,
                expected_generation_id=bootstrap.protocol.generation_id,
                expected_perspective_epoch_id=(
                    bootstrap.perspective.perspective_epoch_id
                ),
            )
            activation_response = await client.post(
                "/game-creation/activate",
                json=activation.model_dump(mode="json"),
                headers=headers,
            )
        return self._validate_worker_response(
            activation_response,
            GameCreationActivateResponse,
            "game_activation_failed",
        )

    async def _require_worker_session(self, game_id: UUID, session_id: UUID) -> None:
        async with self.worker_manager.client(game_id) as client:
            response = await client.post(f"/session/{session_id}/ping")
        if response.status_code != 200:
            raise GatewayError(409, "runtime_session_lost", "Worker session cannot be reattached")

    def _persist_entity_assignments(
        self,
        game: GameRecord,
        membership: MembershipRecord,
        side: GameCreationSideResult,
    ) -> tuple[EntityAssignmentRecord, ...]:
        assignments: list[EntityAssignmentRecord] = []
        try:
            for assignment in side.entity_assignments:
                assignments.append(
                    self.repository.assign_entity(
                        EntityAssignmentCreate(
                            game_id=game.game_id,
                            membership_id=membership.membership_id,
                            entity_uuid=UUID(assignment.entity_uuid),
                            entity_name=assignment.entity_name,
                            faction=assignment.faction,
                            side_id=side.side_id,
                            controller_kind=side.controller,
                            authority_epoch=membership.authority_epoch,
                        )
                    )
                )
        except BaseException:
            for assignment in assignments:
                self.repository.release_entity(assignment.assignment_id)
            raise
        return tuple(assignments)

    def _open_hot_connection(
        self,
        *,
        game: GameRecord,
        membership: MembershipRecord,
        runtime_session_id: UUID,
        controlled_entity_uuids: Iterable[UUID],
        observer_entity_uuids: Iterable[UUID],
        takeover_claim_uuids: Iterable[UUID],
        client_kind: ClientKind,
        client_instance_id: str,
        runtime_base_url: str,
    ) -> HostedGameConnection:
        if game.worker_id is None or game.worker_generation is None:
            raise GatewayError(409, "game_has_no_worker", "Game has no active worker placement")
        controlled = tuple(controlled_entity_uuids)
        observers = tuple(observer_entity_uuids)
        takeover_claims = tuple(takeover_claim_uuids)
        expires_at = datetime.now(UTC) + timedelta(seconds=self.runtime_ttl_seconds)
        issued = self.repository.open_attachment(
            AttachmentCreate(
                runtime_session_id=runtime_session_id,
                game_id=game.game_id,
                membership_id=membership.membership_id,
                worker_id=game.worker_id,
                worker_generation=game.worker_generation,
                client_kind=client_kind,
                client_instance_id=client_instance_id,
                expires_at=expires_at,
                authority_epoch=membership.authority_epoch,
            )
        )
        scopes = _runtime_scopes(membership)
        authority = self.authority_cache.install(
            issued.runtime_token,
            hosted_game_id=game.game_id,
            runtime_session_id=runtime_session_id,
            membership_id=membership.membership_id,
            scopes=scopes,
            controlled_entity_uuids=controlled,
            observer_entity_uuids=observers,
            takeover_claim_uuids=takeover_claims,
            authority_epoch=membership.authority_epoch,
            expires_at=expires_at.timestamp(),
        ).authority
        if authority.active_observer_uuid is None:
            raise GatewayError(
                409,
                "subjective_perspective_unavailable",
                "Runtime attachment has no active subjective observer",
            )
        return HostedGameConnection(
            game_id=game.game_id,
            attachment_id=issued.attachment.attachment_id,
            engine_base_url=runtime_base_url,
            runtime_session_id=runtime_session_id,
            runtime_token=issued.runtime_token,
            membership=membership,
            controlled_entity_uuids=list(controlled),
            observer_entity_uuids=list(observers),
            active_observer_uuid=authority.active_observer_uuid,
            takeover_claim_uuids=list(takeover_claims),
            access_mode=(
                "agent"
                if RuntimeScope.AGENT in scopes
                else "participant"
                if RuntimeScope.CONTROL in scopes
                else "observer"
            ),
            authority_epoch=authority.authority_epoch,
            expires_at=authority.expires_at,
        )

    def _takeover_claims_for_membership(
        self,
        game: GameRecord,
        membership: MembershipRecord,
    ) -> tuple[UUID, ...]:
        """Return claim leases associated with one persisted side membership."""
        if membership.side_id not in {"side_a", "side_b"}:
            return ()
        creation_payload = game.creation_manifest.get("response")
        if not isinstance(creation_payload, dict):
            return ()
        creation = GameCreationStartResponse.model_validate(creation_payload)
        side = creation.side_a if membership.side_id == "side_a" else creation.side_b
        return _side_takeover_claims(side)

    def _observer_entities_for_membership(
        self,
        game: GameRecord,
        membership: MembershipRecord,
        controlled_entity_uuids: Iterable[UUID],
    ) -> tuple[UUID, ...]:
        """Resolve the exact subjective observer union installed in the worker.

        Participant perspectives are intentionally no broader than ownership.
        Zero-control observer seats receive the combatants declared by the
        resolved creation result plus any later directory assignments.  This
        is an explicit union of entity senses, never an objective-state flag.
        """
        controlled = tuple(controlled_entity_uuids)
        if controlled:
            return tuple(sorted(set(controlled), key=str))
        if not membership.capabilities.may_observe_subjective_state:
            return ()

        observers = {
            assignment.entity_uuid
            for assignment in self.repository.list_entity_assignments(game.game_id)
        }
        creation_payload = game.creation_manifest.get("response")
        if not isinstance(creation_payload, dict):
            raise GatewayError(500, "creation_manifest_invalid", "Game has no resolved creation response")
        creation = GameCreationStartResponse.model_validate(creation_payload)
        for side in (creation.side_a, creation.side_b):
            if side is None:
                continue
            observers.update(
                UUID(assignment.entity_uuid)
                for assignment in side.entity_assignments
            )
        if not observers:
            raise GatewayError(
                409,
                "spectator_perspective_unavailable",
                "Observer attachment has no authorized combatant perspective",
            )
        return tuple(sorted(observers, key=str))

    def _require_live_game(self, game: GameRecord) -> None:
        if game.lifecycle_state is not GameLifecycleState.ACTIVE:
            raise GatewayError(409, "game_not_live", "Game is not currently live")
        if self.worker_manager.placement(game.game_id) is None:
            raise GatewayError(409, "worker_not_live", "Game worker is not available")

    def _publish_new_directory_events(self) -> None:
        self.directory_stream.publish_pending()

    def _start_terminal_monitor(self, game_id: UUID) -> None:
        """Watch one worker's objective stream for its terminal barrier."""
        previous = self._terminal_monitors.pop(game_id, None)
        if previous is not None:
            previous.cancel()
        task = asyncio.create_task(
            self._monitor_worker_terminal_event(game_id),
            name=f"terminal-summary-{game_id}",
        )
        self._terminal_monitors[game_id] = task
        task.add_done_callback(lambda completed: self._terminal_monitor_done(game_id, completed))

    async def _reconcile_worker_summary_if_ready(self, game_id: UUID) -> bool:
        """Persist a worker that completed before its live monitor was needed."""
        async with self.worker_manager.client(game_id) as client:
            return await self._persist_worker_summary_if_ready(game_id, client)

    def _terminal_monitor_done(self, game_id: UUID, task: asyncio.Task[None]) -> None:
        """Release a completed terminal monitor and report unexpected failure."""
        if self._terminal_monitors.get(game_id) is task:
            self._terminal_monitors.pop(game_id, None)
        if task.cancelled():
            return
        error = task.exception()
        if error is not None:
            logger.error(
                "terminal summary monitor failed for %s",
                game_id,
                exc_info=(type(error), error, error.__traceback__),
            )

    async def _monitor_worker_terminal_event(self, game_id: UUID) -> None:
        """Reduce persistence from the worker's real EncounterEndEvent stream."""
        async with self.worker_manager.client(game_id, timeout=None) as client:
            if await self._persist_worker_summary_if_ready(game_id, client):
                return

            barrier_response = await client.get(
                "/game/evidence/objective-bootstrap"
            )
            barrier_response.raise_for_status()
            barrier_payload = barrier_response.json()
            since_event = barrier_payload.get("event_cursor")
            since_log = barrier_payload.get("combat_log_cursor")
            if (
                not isinstance(since_event, int)
                or isinstance(since_event, bool)
                or since_event < 0
                or not isinstance(since_log, int)
                or isinstance(since_log, bool)
                or since_log < 0
            ):
                raise GatewayError(
                    502,
                    "worker_objective_barrier_invalid",
                    "Worker objective bootstrap omitted valid cursor barriers",
                )
            # Close the race between the first readiness probe and the cursor
            # capture. If the terminal batch completed in that interval, its
            # evidence is now ready; otherwise subscribing from this exact
            # barrier backfills any later EncounterEndEvent without replaying
            # the whole match.
            if await self._persist_worker_summary_if_ready(game_id, client):
                return

            terminal_event_observed = False
            async with client.stream(
                "GET",
                "/game/evidence/objective-subscribe",
                params={
                    "since_event": since_event,
                    "since_log": since_log,
                },
            ) as response:
                response.raise_for_status()
                event_name: str | None = None
                data_lines: list[str] = []
                async for line in response.aiter_lines():
                    if line.startswith("event:"):
                        event_name = line.removeprefix("event:").strip()
                    elif line.startswith("data:"):
                        data_lines.append(line.removeprefix("data:").strip())
                    elif line == "":
                        if event_name == "game_event" and data_lines:
                            payload = json.loads("\n".join(data_lines))
                            event = payload.get("event", {})
                            if (
                                event.get("event_type") == "encounter_end"
                                and event.get("phase") == "completion"
                            ):
                                terminal_event_observed = True
                                break
                        event_name = None
                        data_lines = []

            if not terminal_event_observed:
                raise GatewayError(
                    502,
                    "terminal_event_stream_ended",
                    "Worker event stream ended before EncounterEndEvent",
                )
            await self._persist_worker_summary_when_ready(game_id, client)

    async def _persist_worker_summary_when_ready(
        self,
        game_id: UUID,
        client: httpx.AsyncClient,
    ) -> None:
        """Persist terminal evidence after its event-batch reducer completes."""
        loop = asyncio.get_running_loop()
        deadline = loop.time() + TERMINAL_SUMMARY_READY_TIMEOUT_SECONDS
        while True:
            if await self._persist_worker_summary_if_ready(game_id, client):
                return
            if loop.time() >= deadline:
                raise GatewayError(
                    502,
                    "terminal_summary_not_ready",
                    "Worker did not publish terminal evidence after EncounterEndEvent",
                )
            await asyncio.sleep(TERMINAL_SUMMARY_RETRY_INTERVAL_SECONDS)

    async def _persist_worker_summary_if_ready(
        self,
        game_id: UUID,
        client: httpx.AsyncClient,
    ) -> bool:
        """Adopt terminal evidence when the durable worker manifest is ready."""
        lock = self._terminal_persistence_locks.setdefault(game_id, asyncio.Lock())
        async with lock:
            return await self._persist_worker_summary_if_ready_under_lock(
                game_id,
                client,
            )

    async def _persist_worker_summary_if_ready_under_lock(
        self,
        game_id: UUID,
        client: httpx.AsyncClient,
    ) -> bool:
        """Adopt the worker's durable ready manifest under the game lock."""

        del client
        game = self.repository.get_game(game_id)
        if game.lifecycle_state is GameLifecycleState.ENDED:
            return True
        try:
            adopted = self._stage_and_adopt_worker_terminal_spool(game)
        except WorkerTerminalSpoolNotReady:
            return False
        except WorkerTerminalSpoolError as exc:
            raise GatewayError(
                502,
                "worker_terminal_spool_invalid",
                str(exc),
            ) from exc
        except TerminalEvidenceError as exc:
            raise GatewayError(502, exc.code, exc.message) from exc
        except ArtifactStoreError as exc:
            raise GatewayError(500, "replay_store_failed", str(exc)) from exc
        if adopted:
            self._publish_new_directory_events()
        return adopted

    @staticmethod
    def _validate_worker_response(
        response: httpx.Response,
        model_type: type[WorkerResponseT],
        code: str,
    ) -> WorkerResponseT:
        if response.status_code >= 400:
            raise GatewayError(response.status_code, code, response.text)
        try:
            # Validate directly from the worker's UTF-8 JSON bytes.  Parsing to
            # an untyped Python graph first duplicates the largest replay
            # allocation and traversal immediately before Pydantic validates
            # the same graph.
            return model_type.model_validate_json(response.content)
        except (ValueError, TypeError) as exc:
            raise GatewayError(502, "worker_contract_invalid", str(exc)) from exc


def create_gateway_app(
    *,
    repository: GameDirectoryRepository | None = None,
    worker_manager: HostedWorkerManager | None = None,
    authority_cache: RuntimeAuthorityCache | None = None,
    artifact_store: GameArtifactStore | None = None,
    capability_pepper: bytes | None = None,
    database_path: Path | None = None,
    runtime_root: Path | None = None,
    artifact_root: Path | None = None,
    worker_application: HostedWorkerApplication | None = None,
) -> FastAPI:
    """Build the multi-game gateway with optional injected test dependencies."""
    if worker_manager is not None and worker_application is not None:
        raise ValueError(
            "worker_application cannot be supplied with an existing worker_manager"
        )
    owns_repository = repository is None
    pepper = capability_pepper or os.environ.get(
        "DND_DIRECTORY_CAPABILITY_PEPPER",
        "local-development-capability-pepper",
    ).encode("utf-8")
    resolved_database_path = database_path or Path(
        os.environ.get("DND_DIRECTORY_DATABASE", ".runtime/game-directory.sqlite3")
    )
    resolved_runtime_root = runtime_root or Path(
        os.environ.get("DND_HOSTED_RUNTIME_ROOT", ".runtime/hosted-games")
    )
    resolved_artifact_root = artifact_root or Path(
        os.environ.get("DND_GAME_ARTIFACT_ROOT", ".runtime/game-artifacts")
    )
    resolved_worker_application = (
        worker_application or CORE_HOSTED_WORKER_APPLICATION
    )
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        loaded_content_system = bootstrap_content_system()
        app.state.content_system = loaded_content_system
        resolved_repository = repository or GameDirectoryRepository(
            resolved_database_path,
            capability_pepper=pepper,
        )
        resolved_workers = worker_manager or HostedWorkerManager(
            resolved_runtime_root,
            worker_application=resolved_worker_application,
            expected_content_set_digest=(
                loaded_content_system.content_set_digest
            ),
            warm_pool_size=int(os.environ.get("DND_HOSTED_WARM_WORKERS", "1")),
        )
        if (
            resolved_workers.expected_content_set_digest
            != loaded_content_system.content_set_digest
        ):
            raise RuntimeError(
                "Gateway content set differs from the configured worker "
                "manager expectation",
            )
        service = GameGatewayService(
            resolved_repository,
            resolved_workers,
            authority_cache or RuntimeAuthorityCache(),
            artifact_store or GameArtifactStore(resolved_artifact_root),
            capability_pepper=pepper,
            content_system=loaded_content_system,
        )
        app.state.gateway = service
        try:
            await resolved_workers.prewarm()
            yield
        finally:
            await service.close()
            await resolved_workers.stop_all()
            if owns_repository:
                resolved_repository.close()

    gateway_app = FastAPI(title="D&D Multi-Game Gateway", lifespan=lifespan)
    gateway_app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    gateway_app.add_middleware(RequestTimingMiddleware)

    @gateway_app.exception_handler(GatewayError)
    async def handle_gateway_error(_request: Request, exc: GatewayError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": {"code": exc.code, "message": exc.message}},
        )

    @gateway_app.exception_handler(DirectoryError)
    async def handle_directory_error(_request: Request, exc: DirectoryError) -> JSONResponse:
        status = 404 if isinstance(exc, NotFoundError) else 403 if isinstance(exc, CapabilityError) else 409 if isinstance(exc, ConflictError) else 500
        return JSONResponse(
            status_code=status,
            content={"detail": {"code": type(exc).__name__, "message": str(exc)}},
        )

    @gateway_app.exception_handler(HostedWorkerError)
    async def handle_worker_error(_request: Request, exc: HostedWorkerError) -> JSONResponse:
        return JSONResponse(
            status_code=502,
            content={"detail": {"code": "hosted_worker_error", "message": str(exc)}},
        )

    @gateway_app.exception_handler(GameCreationCatalogError)
    async def handle_catalog_error(
        _request: Request,
        exc: GameCreationCatalogError,
    ) -> JSONResponse:
        return JSONResponse(status_code=400, content={"detail": exc.detail()})

    def service(request: Request) -> GameGatewayService:
        return request.app.state.gateway

    @gateway_app.get(
        "/server/capabilities",
        response_model=ServerCapabilitiesResponse,
    )
    async def get_server_capabilities() -> ServerCapabilitiesResponse:
        """Return the typed hosted control-plane deployment capabilities."""
        return ServerCapabilitiesResponse(
            server_mode="gateway",
            game_directory_enabled=True,
            persistent_game_history=True,
            isolated_game_workers=True,
        )

    @gateway_app.get(
        "/game-creation/catalog",
        response_model=GameCreationCatalogResponse,
    )
    async def get_game_creation_catalog() -> GameCreationCatalogResponse:
        """Return the shared canonical hosted-game creation catalog."""
        return build_game_creation_catalog()

    @gateway_app.get("/content/manifest", response_model=ContentManifestResponse)
    async def get_content_manifest(
        request: Request,
        response: Response,
    ) -> ContentManifestResponse | Response:
        """Return the exact content identity shared with every worker."""
        manifest = build_content_manifest(request.app.state.content_system)
        etag = content_response_etag(manifest.content_set_digest)
        headers = {
            "ETag": etag,
            "Cache-Control": "public, max-age=0, must-revalidate",
        }
        if request.headers.get("if-none-match") == etag:
            return Response(status_code=304, headers=headers)
        response.headers.update(headers)
        return manifest

    @gateway_app.get("/content/catalog", response_model=ContentCatalogResponse)
    async def get_content_catalog(
        request: Request,
        response: Response,
    ) -> ContentCatalogResponse | Response:
        """Return the shared public descriptor catalog."""
        catalog = build_public_content_catalog(request.app.state.content_system)
        etag = content_response_etag(catalog.catalog_digest)
        headers = {
            "ETag": etag,
            "Cache-Control": "public, max-age=0, must-revalidate",
        }
        if request.headers.get("if-none-match") == etag:
            return Response(status_code=304, headers=headers)
        response.headers.update(headers)
        return catalog

    @gateway_app.post(
        "/game-creation/preflight",
        response_model=CompatibilityReport,
    )
    async def run_game_creation_preflight(
        body: GameCreationPreflightRequest,
    ) -> CompatibilityReport:
        """Validate a hosted-game composition without starting a worker."""
        return preflight_game_creation(body)

    @gateway_app.get("/catalog/spells", response_model=SpellCatalogResponse)
    async def get_spell_catalog() -> SpellCatalogResponse:
        """Return the shared read-only spell and presentation catalog."""
        return build_spell_catalog()

    @gateway_app.post("/directory/principals/guest", response_model=GuestPrincipalResponse)
    async def create_guest(request: Request, body: GuestPrincipalRequest) -> GuestPrincipalResponse:
        return service(request).create_guest_principal(body)

    @gateway_app.post("/directory/players/identify", response_model=PlayerIdentityResponse)
    async def identify_player(
        request: Request,
        body: PlayerIdentityRequest,
    ) -> PlayerIdentityResponse:
        return service(request).identify_player(body)

    @gateway_app.exception_handler(CharacterDirectoryBuildError)
    async def handle_character_build_error(
        _request: Request,
        exc: CharacterDirectoryBuildError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={"detail": exc.validation.model_dump(mode="json")},
        )

    @gateway_app.exception_handler(CharacterDirectoryOwnershipError)
    async def handle_character_ownership_error(
        _request: Request,
        exc: CharacterDirectoryOwnershipError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=403,
            content={
                "detail": {
                    "code": "character_not_owned",
                    "message": str(exc),
                },
            },
        )
    def authorize_character_principal(
        request: Request,
        principal_id: UUID,
        principal_capability: str,
    ) -> UUID:
        return service(request)._authenticate_principal(
            principal_id,
            principal_capability,
        ).principal_id

    gateway_app.include_router(
        create_character_directory_router(
            resolve_service=lambda request: service(request).character_directory,
            authorize_principal=authorize_character_principal,
            on_mutation=lambda request: service(
                request,
            )._publish_new_directory_events(),
        ),
    )

    def resolve_directory_event_filter(
        request: Request,
        principal_id: UUID | None,
        principal_capability: str | None,
    ) -> Callable[[DirectoryEventRecord], bool]:
        return service(request).directory_event_filter(
            principal_id=principal_id,
            principal_capability=principal_capability,
        )

    gateway_app.include_router(
        create_directory_event_stream_router(
            resolve_stream=lambda request: service(
                request,
            ).directory_stream,
            resolve_event_filter=resolve_directory_event_filter,
        )
    )

    def authorize_optional_history_principal(
        request: Request,
        principal_id: UUID | None,
        principal_capability: str | None,
    ) -> UUID | None:
        if principal_id is None and principal_capability is None:
            return None
        if principal_id is None or principal_capability is None:
            raise GatewayError(
                400,
                "incomplete_principal_auth",
                "Both principal fields are required",
            )
        return service(request)._authenticate_principal(
            principal_id,
            principal_capability,
        ).principal_id

    gateway_app.include_router(
        create_game_history_router(
            resolve_service=lambda request: service(request).game_history,
            authorize_optional_principal=(
                authorize_optional_history_principal
            ),
            authorize_required_principal=authorize_character_principal,
        ),
    )

    @gateway_app.post("/games", response_model=CreateHostedGameResponse)
    async def create_game(request: Request, body: CreateHostedGameRequest) -> CreateHostedGameResponse:
        return await service(request).create_hosted_game(
            body,
            public_gateway_base_url=str(request.base_url).rstrip("/"),
        )

    @gateway_app.post("/games/{game_id}/attachments", response_model=AttachHostedGameResponse)
    async def attach_game(
        game_id: UUID,
        request: Request,
        body: AttachHostedGameRequest,
    ) -> AttachHostedGameResponse:
        return await service(request).attach_existing_game(
            game_id,
            body,
            public_gateway_base_url=str(request.base_url).rstrip("/"),
        )

    @gateway_app.post("/games/{game_id}/reconnect", response_model=ReconnectHostedGameResponse)
    async def reconnect_game(
        game_id: UUID,
        request: Request,
        body: ReconnectHostedGameRequest,
    ) -> ReconnectHostedGameResponse:
        return await service(request).reconnect_player(
            game_id,
            body,
            public_gateway_base_url=str(request.base_url).rstrip("/"),
        )

    @gateway_app.post("/games/{game_id}/agent-grants", response_model=CreateAgentGrantResponse)
    async def create_agent_grant(
        game_id: UUID,
        request: Request,
        body: CreateAgentGrantRequest,
    ) -> CreateAgentGrantResponse:
        return service(request).create_remote_agent_grant(game_id, body)

    @gateway_app.post("/games/{game_id}/observers", response_model=ObserveHostedGameResponse)
    async def observe_game(
        game_id: UUID,
        request: Request,
        body: ObserveHostedGameRequest,
    ) -> ObserveHostedGameResponse:
        return await service(request).observe_game(
            game_id,
            body,
            public_gateway_base_url=str(request.base_url).rstrip("/"),
        )

    @gateway_app.post("/games/{game_id}/stop", response_model=StopHostedGameResponse)
    async def stop_game(
        game_id: UUID,
        request: Request,
        body: StopHostedGameRequest,
    ) -> StopHostedGameResponse:
        return await service(request).stop_hosted_game(game_id, body)

    runtime_methods = ["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD"]

    @gateway_app.api_route(
        "/games/{game_id}/runtime/{worker_path:path}",
        methods=runtime_methods,
    )
    async def runtime_proxy(game_id: UUID, worker_path: str, request: Request):
        gateway = service(request)
        return await proxy_runtime_request(
            request,
            hosted_game_id=game_id,
            worker_path=worker_path,
            worker_manager=gateway.worker_manager,
            authority_cache=gateway.authority_cache,
        )

    return gateway_app


def _selected_side(
    creation: GameCreationStartResponse,
    owner_side: str,
) -> GameCreationSideResult | None:
    if owner_side == "side_a":
        return creation.side_a
    if owner_side == "side_b":
        return creation.side_b
    return None


def _character_matches_deployment_snapshot(
    character: CharacterRecord,
    deployment: CharacterDeploymentSnapshot,
) -> bool:
    """Check the revision triplet bound before worker preparation."""

    return (
        character.character_id == deployment.character_id
        and character.row_version == deployment.character_row_version
        and character.current_definition_revision
        == deployment.definition.definition_revision
        and character.current_definition_digest
        == deployment.definition.definition_digest
        and character.current_holdings_revision
        == deployment.holdings.holdings_revision
        and character.current_holdings_digest
        == deployment.holdings.holdings_digest
        and character.current_loadout_revision
        == deployment.loadout.loadout_revision
        and character.current_loadout_digest
        == deployment.loadout.loadout_digest
    )


def _side_takeover_claims(side: GameCreationSideResult | None) -> tuple[UUID, ...]:
    """Return the controller lease exposed by one configured Codex side."""
    if side is None or side.takeover_claim_id is None:
        return ()
    return (UUID(side.takeover_claim_id),)


def _scenario_id(request: CreateHostedGameRequest) -> str:
    scenario = request.creation.scenario
    if scenario.kind == "preset":
        return scenario.arena_id
    return ":".join((
        scenario.hero_configuration_id,
        scenario.monster_configuration_id,
        scenario.battlefield_id,
        scenario.deployment_id,
    ))


def _owner_capabilities(controls_entities: bool, agent: bool) -> MembershipCapabilities:
    return MembershipCapabilities(
        may_connect=True,
        may_observe_public_state=True,
        may_observe_subjective_state=True,
        may_control_entities=controls_entities,
        may_view_agent_telemetry=agent,
        may_manage_members=True,
        may_manage_game=True,
        may_view_objective_replay=True,
    )


def _observer_capabilities() -> MembershipCapabilities:
    return MembershipCapabilities(
        may_connect=True,
        may_observe_public_state=True,
        may_observe_subjective_state=True,
        may_view_objective_replay=False,
    )


def _agent_capabilities() -> MembershipCapabilities:
    return MembershipCapabilities(
        may_connect=True,
        may_observe_public_state=True,
        may_observe_subjective_state=True,
        may_control_entities=True,
        may_view_agent_telemetry=True,
        may_view_objective_replay=False,
    )


def _runtime_scopes(membership: MembershipRecord) -> frozenset[RuntimeScope]:
    scopes: set[RuntimeScope]
    if (
        membership.role is MembershipRole.AGENT
        or membership.controller_kind == "codex"
    ):
        scopes = {RuntimeScope.AGENT}
    else:
        scopes = {RuntimeScope.OBSERVE}
    if membership.capabilities.may_observe_subjective_state:
        scopes.add(RuntimeScope.SUBJECTIVE_OBSERVE)
    if membership.capabilities.may_control_entities:
        scopes.add(RuntimeScope.CONTROL)
    if membership.capabilities.may_view_agent_telemetry or membership.role is MembershipRole.AGENT:
        scopes.add(RuntimeScope.AGENT)
    if membership.capabilities.may_manage_game:
        scopes.add(RuntimeScope.ADMINISTER)
    return frozenset(scopes)


app = create_gateway_app()
