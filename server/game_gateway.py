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
from fastapi import FastAPI, Header, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

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
from server.directory_event_stream import DirectoryEventStream
from server.event_contract import EVENT_CONTRACT_HASH
from server.game_directory.canonical import canonical_digest, hash_capability
from server.game_directory.contracts import (
    AccessGrantCreate,
    ArtifactCreate,
    ArtifactKind,
    AttachmentState,
    AttachmentCreate,
    CharacterCreate,
    CharacterDeploymentCreate,
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
    PrincipalCreate,
    PrincipalCredentialCreate,
    PrincipalKind,
    PrincipalRecord,
    ProducerKind,
    VisibilityPolicy,
    WorkerCreate,
    WorkerState,
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
    AttachmentSummary,
    AttachHostedGameRequest,
    AttachHostedGameResponse,
    CreateCharacterRequest,
    CreateAgentGrantRequest,
    CreateAgentGrantResponse,
    CreateHostedGameRequest,
    CreateHostedGameResponse,
    GuestPrincipalRequest,
    GuestPrincipalResponse,
    HostedGameConnection,
    HostedGameListResponse,
    ObserveHostedGameRequest,
    ObserveHostedGameResponse,
    PlayerGameSeat,
    PlayerIdentityRequest,
    PlayerIdentityResponse,
    PlayerProfileResponse,
    ReconnectHostedGameRequest,
    ReconnectHostedGameResponse,
    StopHostedGameRequest,
    StopHostedGameResponse,
)
from dnd.scenarios.evaluation.combatant_catalog import get_combatant_configuration
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
from server.objective_replay import (
    OBJECTIVE_REPLAY_CONTRACT_HASH,
    OBJECTIVE_REPLAY_CONTRACT_VERSION,
    ObjectiveReplayBundle,
)
from server.player_replay import (
    PLAYER_REPLAY_CONTRACT_HASH,
    PLAYER_REPLAY_CONTRACT_VERSION,
    SubjectivePlayerReplayArchive,
    SubjectivePlayerReplayBundle,
)
from server.runtime_authority import (
    RuntimeAuthorityCache,
    RuntimeScope,
    runtime_projection_headers,
)
from server.request_timing import RequestTimingMiddleware
from server.spell_catalog import build_spell_catalog
from server.worker_proxy import proxy_runtime_request


ENGINE_VERSION = "0.1.0"
RULESET_VERSION = "single-videogame-ruleset-v1"
DEFAULT_RUNTIME_TTL_SECONDS = 60 * 60
TERMINAL_SUMMARY_READY_TIMEOUT_SECONDS = 5.0
TERMINAL_SUMMARY_RETRY_INTERVAL_SECONDS = 0.01
OBJECTIVE_REPLAY_SCHEMA_VERSION = (
    f"dnd.objective-replay.v{OBJECTIVE_REPLAY_CONTRACT_VERSION}."
    f"{OBJECTIVE_REPLAY_CONTRACT_HASH}"
)
SUBJECTIVE_REPLAY_SCHEMA_VERSION = (
    f"dnd.subjective-player-replay.v{PLAYER_REPLAY_CONTRACT_VERSION}."
    f"{PLAYER_REPLAY_CONTRACT_HASH}"
)
PERSISTENT_CHARACTER_PRESET_IDS = frozenset(
    {
        "hero.barbarian_l5_berserker_torch",
        "hero.fighter_l5_shield_torch",
        "hero.sorcerer_l5_standard_torch",
    }
)
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
        runtime_ttl_seconds: int = DEFAULT_RUNTIME_TTL_SECONDS,
    ) -> None:
        self.repository = repository
        self.worker_manager = worker_manager
        self.authority_cache = authority_cache
        self.artifact_store = artifact_store
        self.capability_pepper = capability_pepper
        self.runtime_ttl_seconds = runtime_ttl_seconds
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
                    self.repository.transition_game(
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
        """Mark durable active rows whose worker is absent after gateway start."""
        for game in self.repository.list_games(
            lifecycle_state=GameLifecycleState.ACTIVE,
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
            self.repository.transition_game(
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
        self._publish_new_directory_events()
        return PlayerIdentityResponse(
            principal=principal,
            credential_id=credential.credential_id,
            principal_capability=capability,
        )

    def get_player_profile(
        self,
        principal_id: UUID,
        principal_capability: str,
    ) -> PlayerProfileResponse:
        """Return identity-owned characters and game seats."""

        principal = self._authenticate_principal(principal_id, principal_capability)
        characters = list(self.repository.list_characters_for_principal(principal_id))
        seats: list[PlayerGameSeat] = []
        for membership in self.repository.list_memberships_for_principal(principal_id):
            controlled = [
                assignment.entity_uuid
                for assignment in self.repository.list_entity_assignments(
                    membership.game_id,
                    active_only=False,
                )
                if assignment.membership_id == membership.membership_id
                and assignment.released_at is None
            ]
            attachments = self.repository.list_attachments_for_membership(
                membership.membership_id,
                connected_only=True,
            )
            seats.append(
                PlayerGameSeat(
                    membership=membership,
                    controlled_entity_uuids=controlled,
                    active_attachments=[
                        AttachmentSummary(
                            attachment_id=attachment.attachment_id,
                            game_id=attachment.game_id,
                            membership_id=attachment.membership_id,
                            client_kind=attachment.client_kind,
                            client_instance_id=attachment.client_instance_id,
                            connected_at=attachment.connected_at,
                            expires_at=attachment.expires_at,
                        )
                        for attachment in attachments
                    ],
                )
            )
        return PlayerProfileResponse(
            principal=principal,
            characters=characters,
            game_seats=seats,
        )

    def create_character(
        self,
        principal_id: UUID,
        principal_capability: str,
        request: CreateCharacterRequest,
    ) -> CharacterRecord:
        """Create one preset-backed persistent character for a player."""

        self._authenticate_principal(principal_id, principal_capability)
        if request.preset_configuration_id not in PERSISTENT_CHARACTER_PRESET_IDS:
            raise GatewayError(
                400,
                "character_preset_unsupported",
                "Character preset is not available for persistent player characters",
            )
        configuration = get_combatant_configuration(request.preset_configuration_id)
        if configuration.side_kind != "hero" or len(configuration.members) != 1:
            raise GatewayError(
                400,
                "character_preset_invalid",
                "Persistent characters require a single-member hero configuration",
            )
        display_name = " ".join(request.display_name.split())
        if not display_name:
            raise GatewayError(400, "character_name_empty", "Character name cannot be blank")
        character = self.repository.create_character(
            CharacterCreate(
                owner_principal_id=principal_id,
                display_name=display_name,
                preset_configuration_id=request.preset_configuration_id,
            )
        )
        self._publish_new_directory_events()
        return character

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
        if request.character_id is not None:
            character = self.repository.get_character(request.character_id)
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
                request.creation.scenario.hero_configuration_id
                != character.preset_configuration_id
            ):
                raise GatewayError(
                    400,
                    "character_preset_mismatch",
                    "Game hero configuration does not match the selected character",
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
                    },
                    ruleset_version=RULESET_VERSION,
                    engine_version=ENGINE_VERSION,
                    content_digest=canonical_digest(request.creation),
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
                if side is None or len(side.entity_assignments) != 1:
                    raise GatewayError(
                        409,
                        "character_deployment_ambiguous",
                        "Persistent character deployment requires exactly one hero entity",
                    )
                self.repository.deploy_character(
                    CharacterDeploymentCreate(
                        game_id=game.game_id,
                        membership_id=membership.membership_id,
                        character_id=character.character_id,
                        entity_uuid=UUID(side.entity_assignments[0].entity_uuid),
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
                self.repository.transition_game(
                    game.game_id,
                    expected_row_version=game.row_version,
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
            game = self.repository.transition_game(
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
    ) -> HostedGameListResponse:
        """List public games plus private games belonging to an authenticated principal."""
        visible_principal: PrincipalRecord | None = None
        if principal_id is not None or principal_capability is not None:
            if principal_id is None or principal_capability is None:
                raise GatewayError(400, "incomplete_principal_auth", "Both principal fields are required")
            visible_principal = self._authenticate_principal(principal_id, principal_capability)
        games = self.repository.list_games(limit=500)
        visible: list[GameRecord] = []
        for game in games:
            if game.visibility_policy is VisibilityPolicy.PUBLIC:
                visible.append(game)
                continue
            if visible_principal is None:
                continue
            if any(
                membership.principal_id == visible_principal.principal_id
                and membership.membership_state is MembershipState.ACTIVE
                for membership in self.repository.list_memberships(game.game_id)
            ):
                visible.append(game)
        return HostedGameListResponse(games=visible, count=len(visible))

    def require_visible_game(
        self,
        game_id: UUID,
        *,
        principal_id: UUID | None,
        principal_capability: str | None,
    ) -> GameRecord:
        """Return a game only when directory visibility permits discovery."""
        game = self.repository.get_game(game_id)
        if game.visibility_policy is VisibilityPolicy.PUBLIC:
            return game
        if principal_id is None or principal_capability is None:
            raise GatewayError(404, "game_not_found", "Game was not found")
        principal = self._authenticate_principal(principal_id, principal_capability)
        if not any(
            membership.principal_id == principal.principal_id
            and membership.membership_state is MembershipState.ACTIVE
            for membership in self.repository.list_memberships(game_id)
        ):
            raise GatewayError(404, "game_not_found", "Game was not found")
        return game

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
        game = self.repository.get_game(game_id)
        if game.lifecycle_state not in {
            GameLifecycleState.ENDED,
            GameLifecycleState.ARCHIVED,
        }:
            raise GatewayError(
                409,
                "objective_replay_not_terminal",
                "Objective replay is available only for ended or archived games",
            )
        authorized = any(
            membership.principal_id == principal.principal_id
            and membership.membership_state in {
                MembershipState.ACTIVE,
                MembershipState.DISCONNECTED,
            }
            and membership.capabilities.may_view_objective_replay
            for membership in self.repository.list_memberships(game_id)
        )
        if not authorized:
            raise GatewayError(
                403,
                "objective_replay_denied",
                "Principal may not read objective replay evidence",
            )

        artifacts = self.repository.list_artifacts(
            game_id,
            artifact_kind=ArtifactKind.REPLAY_BUNDLE,
        )
        if not artifacts:
            raise GatewayError(404, "objective_replay_missing", "Objective replay was not found")
        if len(artifacts) != 1:
            raise GatewayError(409, "objective_replay_ambiguous", "Multiple objective replays are registered")
        artifact = artifacts[0]
        if (
            artifact.schema_version != OBJECTIVE_REPLAY_SCHEMA_VERSION
            or artifact.media_type != "application/json"
        ):
            raise GatewayError(500, "objective_replay_metadata_invalid", "Replay metadata contract is invalid")
        try:
            payload = self.artifact_store.read_bytes(artifact.content_digest)
        except ArtifactStoreError as exc:
            raise GatewayError(500, "objective_replay_integrity_failed", str(exc)) from exc
        if len(payload) != artifact.byte_size:
            raise GatewayError(500, "objective_replay_size_mismatch", "Replay byte size does not match metadata")
        try:
            replay = ObjectiveReplayBundle.model_validate_json(payload)
        except ValueError as exc:
            raise GatewayError(500, "objective_replay_contract_invalid", str(exc)) from exc
        if replay.game_id != str(game_id):
            raise GatewayError(500, "objective_replay_game_mismatch", "Replay belongs to another game")
        summary = self.repository.get_current_summary(game_id).summary
        if replay.encounter_uuid != str(summary.encounter_uuid):
            raise GatewayError(
                500,
                "objective_replay_encounter_mismatch",
                "Replay describes another encounter",
            )
        if (
            replay.terminal_event_cursor != game.final_event_cursor
            or replay.terminal_combat_log_cursor != game.final_combat_log_cursor
        ):
            raise GatewayError(500, "objective_replay_cursor_mismatch", "Replay disagrees with terminal game cursors")
        return replay

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
        game = self.repository.get_game(game_id)
        if game.lifecycle_state not in {
            GameLifecycleState.ENDED,
            GameLifecycleState.ARCHIVED,
        }:
            raise GatewayError(
                409,
                "subjective_replay_not_terminal",
                "Player replay is available only for ended or archived games",
            )
        try:
            membership = self.repository.get_membership(membership_id)
        except NotFoundError as exc:
            raise GatewayError(
                404,
                "subjective_replay_membership_not_found",
                "Game membership was not found",
            ) from exc
        if (
            membership.game_id != game_id
            or membership.principal_id != principal.principal_id
            or membership.membership_state
            not in {MembershipState.ACTIVE, MembershipState.DISCONNECTED}
            or not membership.capabilities.may_observe_subjective_state
        ):
            raise GatewayError(
                403,
                "subjective_replay_denied",
                "Principal may not read this membership's player replay",
            )

        archive = self._read_subjective_replay_archive(game_id)
        replay = next(
            (
                candidate
                for candidate in archive.membership_replays
                if candidate.membership_id == str(membership_id)
            ),
            None,
        )
        if replay is None:
            raise GatewayError(
                404,
                "subjective_replay_missing",
                "No canonical player replay was recorded for this membership",
            )
        return replay

    def _read_subjective_replay_archive(
        self,
        game_id: UUID,
    ) -> SubjectivePlayerReplayArchive:
        """Read and authenticate one aggregate archive without exposing it publicly."""

        game = self.repository.get_game(game_id)
        artifacts = self.repository.list_artifacts(
            game_id,
            artifact_kind=ArtifactKind.SUBJECTIVE_REPLAY_BUNDLE,
        )
        if not artifacts:
            raise GatewayError(
                404,
                "subjective_replay_archive_missing",
                "Player replay archive was not found",
            )
        if len(artifacts) != 1:
            raise GatewayError(
                409,
                "subjective_replay_archive_ambiguous",
                "Multiple player replay archives are registered",
            )
        artifact = artifacts[0]
        if (
            artifact.schema_version != SUBJECTIVE_REPLAY_SCHEMA_VERSION
            or artifact.media_type != "application/json"
        ):
            raise GatewayError(
                500,
                "subjective_replay_metadata_invalid",
                "Player replay metadata contract is invalid",
            )
        try:
            payload = self.artifact_store.read_bytes(artifact.content_digest)
        except ArtifactStoreError as exc:
            raise GatewayError(
                500,
                "subjective_replay_integrity_failed",
                str(exc),
            ) from exc
        if len(payload) != artifact.byte_size:
            raise GatewayError(
                500,
                "subjective_replay_size_mismatch",
                "Player replay byte size does not match metadata",
            )
        try:
            archive = SubjectivePlayerReplayArchive.model_validate_json(payload)
        except ValueError as exc:
            raise GatewayError(
                500,
                "subjective_replay_contract_invalid",
                str(exc),
            ) from exc
        if archive.game_id != str(game_id):
            raise GatewayError(
                500,
                "subjective_replay_game_mismatch",
                "Player replay archive belongs to another game",
            )
        summary = self.repository.get_current_summary(game_id).summary
        if archive.encounter_uuid != str(summary.encounter_uuid):
            raise GatewayError(
                500,
                "subjective_replay_encounter_mismatch",
                "Player replay archive describes another encounter",
            )
        if (
            archive.terminal_source_event_cursor != game.final_event_cursor
            or archive.terminal_combat_log_cursor != game.final_combat_log_cursor
        ):
            raise GatewayError(
                500,
                "subjective_replay_cursor_mismatch",
                "Player replay archive disagrees with terminal game cursors",
            )
        return archive

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

        def event_is_visible(event: DirectoryEventRecord) -> bool:
            if event.game_id is None:
                return False
            try:
                game = self.repository.get_game(event.game_id)
            except NotFoundError:
                return False
            if game.visibility_policy is VisibilityPolicy.PUBLIC:
                return True
            if visible_principal is None:
                return False
            return any(
                membership.principal_id == visible_principal.principal_id
                and membership.membership_state is MembershipState.ACTIVE
                for membership in self.repository.list_memberships(event.game_id)
            )

        return event_is_visible

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
        for event in self.repository.list_directory_events(
            since_cursor=self.directory_stream.cursor,
            limit=1000,
        ):
            self.directory_stream.publish(event)

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
        """Persist terminal evidence and report whether all three inputs are ready."""
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
        """Fetch and publish terminal evidence while the game lock is held."""
        summary_response = await client.get("/game/evidence/summary")
        if summary_response.status_code == 404:
            detail = summary_response.json().get("detail", {})
            if detail.get("code") == "terminal_summary_not_ready":
                return False
        summary_response.raise_for_status()

        objective_replay_response = await client.get(
            "/game/evidence/objective-replay"
        )
        if objective_replay_response.status_code == 404:
            detail = objective_replay_response.json().get("detail", {})
            if detail.get("code") == "terminal_objective_replay_not_ready":
                return False
        objective_replay_response.raise_for_status()

        subjective_replay_response = await client.get(
            "/game/evidence/subjective-replay"
        )
        if subjective_replay_response.status_code == 404:
            detail = subjective_replay_response.json().get("detail", {})
            if detail.get("code") == "terminal_subjective_replay_not_ready":
                return False
        subjective_replay_response.raise_for_status()
        self._publish_worker_terminal_responses(
            game_id,
            summary_response=summary_response,
            objective_replay_response=objective_replay_response,
            subjective_replay_response=subjective_replay_response,
        )
        return True

    def _publish_worker_terminal_responses(
        self,
        game_id: UUID,
        *,
        summary_response: httpx.Response,
        objective_replay_response: httpx.Response,
        subjective_replay_response: httpx.Response,
    ) -> None:
        """Validate, store, and atomically publish both replays plus summary."""
        evidence = self._validate_worker_response(
            summary_response,
            WorkerSummaryEvidence,
            "worker_summary_invalid",
        )
        replay = self._validate_worker_response(
            objective_replay_response,
            ObjectiveReplayBundle,
            "worker_replay_invalid",
        )
        subjective_replay = self._validate_worker_response(
            subjective_replay_response,
            SubjectivePlayerReplayArchive,
            "worker_subjective_replay_invalid",
        )
        if evidence.summary.game_id != str(game_id):
            raise GatewayError(502, "summary_game_mismatch", "Worker summary belongs to another game")
        if replay.game_id != str(game_id):
            raise GatewayError(502, "replay_game_mismatch", "Worker replay belongs to another game")
        if subjective_replay.game_id != str(game_id):
            raise GatewayError(
                502,
                "subjective_replay_game_mismatch",
                "Worker player replay belongs to another game",
            )
        if replay.encounter_uuid != str(evidence.summary.encounter_uuid):
            raise GatewayError(502, "replay_encounter_mismatch", "Replay and summary describe different encounters")
        if subjective_replay.encounter_uuid != str(evidence.summary.encounter_uuid):
            raise GatewayError(
                502,
                "subjective_replay_encounter_mismatch",
                "Player replay and summary describe different encounters",
            )
        if replay.generation_id != str(evidence.generation_id):
            raise GatewayError(502, "replay_generation_mismatch", "Replay and summary use different generations")
        if (
            replay.terminal_event_cursor != evidence.summary.terminal_cursor.event_cursor
            or replay.terminal_combat_log_cursor
            != evidence.summary.terminal_cursor.combat_log_cursor
        ):
            raise GatewayError(502, "replay_cursor_mismatch", "Replay and summary terminal cursors differ")
        if (
            subjective_replay.terminal_source_event_cursor
            != evidence.summary.terminal_cursor.event_cursor
            or subjective_replay.terminal_combat_log_cursor
            != evidence.summary.terminal_cursor.combat_log_cursor
        ):
            raise GatewayError(
                502,
                "subjective_replay_cursor_mismatch",
                "Player replay and summary terminal cursors differ",
            )
        known_membership_ids = {
            str(membership.membership_id)
            for membership in self.repository.list_memberships(game_id)
        }
        replay_membership_ids = {
            bundle.membership_id
            for bundle in subjective_replay.membership_replays
        }
        if not replay_membership_ids.issubset(known_membership_ids):
            raise GatewayError(
                502,
                "subjective_replay_membership_mismatch",
                "Player replay contains an unknown or cross-game membership",
            )

        try:
            stored = self.artifact_store.put_json(replay)
        except ArtifactStoreError as exc:
            raise GatewayError(500, "replay_store_failed", str(exc)) from exc
        try:
            stored_subjective = self.artifact_store.put_json(subjective_replay)
        except ArtifactStoreError as exc:
            raise GatewayError(
                500,
                "subjective_replay_store_failed",
                str(exc),
            ) from exc
        replay_artifact = ArtifactCreate(
            game_id=game_id,
            artifact_kind=ArtifactKind.REPLAY_BUNDLE,
            schema_version=OBJECTIVE_REPLAY_SCHEMA_VERSION,
            media_type="application/json",
            uri=stored.uri,
            byte_size=stored.byte_size,
            content_digest=stored.content_digest,
            producer_kind=ProducerKind.WORKER,
            producer_version=ENGINE_VERSION,
        )
        subjective_replay_artifact = ArtifactCreate(
            game_id=game_id,
            artifact_kind=ArtifactKind.SUBJECTIVE_REPLAY_BUNDLE,
            schema_version=SUBJECTIVE_REPLAY_SCHEMA_VERSION,
            media_type="application/json",
            uri=stored_subjective.uri,
            byte_size=stored_subjective.byte_size,
            content_digest=stored_subjective.content_digest,
            producer_kind=ProducerKind.WORKER,
            producer_version=ENGINE_VERSION,
        )
        self.repository.publish_terminal_evidence(
            replay_artifact,
            evidence.summary,
            additional_artifacts=(subjective_replay_artifact,),
            summary_revision=1,
            source_event_digest=evidence.source_event_digest,
            source_combat_log_digest=evidence.source_combat_log_digest,
        )
        self._publish_new_directory_events()

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
        resolved_repository = repository or GameDirectoryRepository(
            resolved_database_path,
            capability_pepper=pepper,
        )
        resolved_workers = worker_manager or HostedWorkerManager(
            resolved_runtime_root,
            worker_application=resolved_worker_application,
            warm_pool_size=int(os.environ.get("DND_HOSTED_WARM_WORKERS", "1")),
        )
        service = GameGatewayService(
            resolved_repository,
            resolved_workers,
            authority_cache or RuntimeAuthorityCache(),
            artifact_store or GameArtifactStore(resolved_artifact_root),
            capability_pepper=pepper,
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

    @gateway_app.get("/directory/players/me", response_model=PlayerProfileResponse)
    async def get_player_profile(
        request: Request,
        principal_id: UUID = Header(alias="X-Dnd-Principal-Id"),
        principal_capability: str = Header(alias="X-Dnd-Principal-Capability"),
    ) -> PlayerProfileResponse:
        return service(request).get_player_profile(principal_id, principal_capability)

    @gateway_app.post("/directory/characters", response_model=CharacterRecord)
    async def create_character(
        request: Request,
        body: CreateCharacterRequest,
        principal_id: UUID = Header(alias="X-Dnd-Principal-Id"),
        principal_capability: str = Header(alias="X-Dnd-Principal-Capability"),
    ) -> CharacterRecord:
        return service(request).create_character(
            principal_id,
            principal_capability,
            body,
        )

    @gateway_app.get("/games", response_model=HostedGameListResponse)
    async def list_games(
        request: Request,
        principal_id: UUID | None = Header(default=None, alias="X-Dnd-Principal-Id"),
        principal_capability: str | None = Header(
            default=None,
            alias="X-Dnd-Principal-Capability",
        ),
    ) -> HostedGameListResponse:
        return service(request).list_visible_games(
            principal_id=principal_id,
            principal_capability=principal_capability,
        )

    @gateway_app.get("/games/subscribe")
    async def subscribe_games(
        request: Request,
        since: int = 0,
        principal_id: UUID | None = Header(default=None, alias="X-Dnd-Principal-Id"),
        principal_capability: str | None = Header(
            default=None,
            alias="X-Dnd-Principal-Capability",
        ),
    ) -> StreamingResponse:
        gateway = service(request)
        stream = gateway.directory_stream
        event_filter = gateway.directory_event_filter(
            principal_id=principal_id,
            principal_capability=principal_capability,
        )
        return StreamingResponse(
            stream.iterate(
                since=since,
                disconnected=request.is_disconnected,
                event_filter=event_filter,
            ),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    @gateway_app.post("/games", response_model=CreateHostedGameResponse)
    async def create_game(request: Request, body: CreateHostedGameRequest) -> CreateHostedGameResponse:
        return await service(request).create_hosted_game(
            body,
            public_gateway_base_url=str(request.base_url).rstrip("/"),
        )

    @gateway_app.get("/games/{game_id}", response_model=GameRecord)
    async def get_game(
        game_id: UUID,
        request: Request,
        principal_id: UUID | None = Header(default=None, alias="X-Dnd-Principal-Id"),
        principal_capability: str | None = Header(
            default=None,
            alias="X-Dnd-Principal-Capability",
        ),
    ) -> GameRecord:
        return service(request).require_visible_game(
            game_id,
            principal_id=principal_id,
            principal_capability=principal_capability,
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

    @gateway_app.get("/games/{game_id}/summary")
    async def get_summary(
        game_id: UUID,
        request: Request,
        principal_id: UUID | None = Header(default=None, alias="X-Dnd-Principal-Id"),
        principal_capability: str | None = Header(
            default=None,
            alias="X-Dnd-Principal-Capability",
        ),
    ):
        gateway = service(request)
        gateway.require_visible_game(
            game_id,
            principal_id=principal_id,
            principal_capability=principal_capability,
        )
        return gateway.repository.get_current_summary(game_id)

    @gateway_app.get(
        "/games/{game_id}/diagnostics/objective-replay",
        response_model=ObjectiveReplayBundle,
    )
    async def get_objective_replay(
        game_id: UUID,
        request: Request,
        response: Response,
        principal_id: UUID = Header(alias="X-Dnd-Principal-Id"),
        principal_capability: str = Header(alias="X-Dnd-Principal-Capability"),
    ) -> ObjectiveReplayBundle:
        replay = service(request).get_objective_replay(
            game_id,
            principal_id=principal_id,
            principal_capability=principal_capability,
        )
        response.headers["Cache-Control"] = "private, no-store"
        return replay

    @gateway_app.get(
        "/games/{game_id}/memberships/{membership_id}/replay",
        response_model=SubjectivePlayerReplayBundle,
    )
    async def get_subjective_replay(
        game_id: UUID,
        membership_id: UUID,
        request: Request,
        response: Response,
        principal_id: UUID = Header(alias="X-Dnd-Principal-Id"),
        principal_capability: str = Header(alias="X-Dnd-Principal-Capability"),
    ) -> SubjectivePlayerReplayBundle:
        replay = service(request).get_subjective_replay(
            game_id,
            membership_id,
            principal_id=principal_id,
            principal_capability=principal_capability,
        )
        response.headers["Cache-Control"] = "private, no-store"
        return replay

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
