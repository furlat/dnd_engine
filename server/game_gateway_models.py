"""Public Pydantic contracts for the multi-game gateway."""

from __future__ import annotations

from enum import Enum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from server.api_models import GameCreationStartRequest, GameCreationStartResponse
from server.game_directory.contracts import (
    ClientKind,
    GameRecord,
    MembershipRecord,
    ObserverPolicy,
    PrincipalRecord,
    VisibilityPolicy,
)


class GatewayModel(BaseModel):
    """Strict base model for gateway request and response contracts."""

    model_config = ConfigDict(extra="forbid")


class AttachmentPolicy(str, Enum):
    """How a new browser attachment affects existing attachments."""

    PARALLEL = "parallel"
    REPLACE_EXISTING = "replace_existing"


class PlayerIdentityRequest(GatewayModel):
    """Resolve one local-trust player name to a durable principal."""

    display_name: str = Field(min_length=1, max_length=80, description="Temporary name-only login.")
    client_instance_id: str = Field(min_length=1, max_length=160, description="Browser instance receiving a credential.")


class PlayerIdentityResponse(GatewayModel):
    """Durable player identity plus one independently revocable client credential."""

    principal: PrincipalRecord = Field(description="Stable player principal.")
    credential_id: UUID = Field(description="Credential issued to this browser instance.")
    principal_capability: str = Field(min_length=32, description="Secret browser credential.")
    authentication_kind: Literal["name_only_local"] = Field(
        default="name_only_local",
        description="Explicitly weak authentication mode used during local development.",
    )


class GuestPrincipalRequest(GatewayModel):
    """Create one local capability-backed directory identity."""

    display_name: str = Field(min_length=1, max_length=80, description="Player-facing identity name.")


class GuestPrincipalResponse(GatewayModel):
    """One-time principal credential response."""

    principal: PrincipalRecord = Field(description="Persisted non-secret principal metadata.")
    principal_capability: str = Field(
        min_length=32,
        description="Secret principal capability returned only at identity creation.",
    )


class CreateHostedGameRequest(GatewayModel):
    """Create one isolated game and attach its owner."""

    principal_id: UUID = Field(description="Principal creating and owning the game.")
    principal_capability: str = Field(min_length=32, description="Owner identity capability.")
    display_name: str = Field(min_length=1, max_length=120, description="Directory display name.")
    creation: GameCreationStartRequest = Field(description="Canonical worker game-creation request.")
    owner_roster_slot_id: str | None = Field(
        default=None,
        min_length=1,
        description=(
            "Roster whose human-controlled members belong to the owner; "
            "null creates an observer-only attachment."
        ),
    )
    visibility_policy: VisibilityPolicy = Field(
        default=VisibilityPolicy.PRIVATE,
        description="Directory discovery policy.",
    )
    observer_policy: ObserverPolicy = Field(
        default=ObserverPolicy.DISABLED,
        description="Policy for future observer attachments.",
    )
    client_kind: ClientKind = Field(
        default=ClientKind.NEUROCLIENT,
        description="Kind of client receiving the initial attachment.",
    )
    client_instance_id: str = Field(
        min_length=1,
        max_length=160,
        description="Client-generated browser or process identity.",
    )


class HostedGameConnection(GatewayModel):
    """Hot game-scoped runtime connection returned by a cold handshake."""

    game_id: UUID = Field(description="Directory game identity.")
    attachment_id: UUID = Field(description="Concrete browser/process attachment identity.")
    engine_base_url: str = Field(description="Game-scoped SDK base URL.")
    runtime_session_id: UUID = Field(description="Worker session identifier.")
    runtime_token: str = Field(min_length=32, description="Short-lived runtime bearer capability.")
    membership: MembershipRecord = Field(description="Durable authority represented by this connection.")
    controlled_entity_uuids: list[UUID] = Field(
        default_factory=list,
        description="Entities this runtime may command.",
    )
    observer_entity_uuids: list[UUID] = Field(
        default_factory=list,
        description="Explicit entity senses this runtime may combine for subjective replication.",
    )
    active_observer_uuid: UUID = Field(
        description="Observer selected for focus within the authorized subjective union.",
    )
    access_mode: Literal["participant", "observer"] = Field(
        description="Client access mode.",
    )
    authority_epoch: int = Field(ge=1, description="Authority version installed in gateway memory.")
    expires_at: float = Field(description="Runtime token expiration as Unix time.")


class CreateHostedGameResponse(GatewayModel):
    """Created directory game, worker result, and initial owner attachment."""

    game: GameRecord = Field(description="Durable hosted-game record.")
    creation: GameCreationStartResponse = Field(description="Exact worker game-creation result.")
    connection: HostedGameConnection = Field(description="Initial owner runtime connection.")
    reconnect_grant_id: UUID = Field(description="Identifier of the durable reconnect capability.")
    reconnect_capability: str = Field(
        min_length=32,
        description="Secret reconnect capability returned only to its owner.",
    )


class AttachHostedGameRequest(GatewayModel):
    """Redeem a reconnect or invite grant for a new runtime attachment."""

    grant_id: UUID = Field(description="Directory access-grant identifier.")
    capability: str = Field(min_length=32, description="Secret access-grant capability.")
    client_kind: ClientKind = Field(description="Kind of reconnecting client.")
    client_instance_id: str = Field(min_length=1, max_length=160, description="Client instance identity.")


class AttachHostedGameResponse(GatewayModel):
    """Fresh hot connection for an existing durable membership."""

    game: GameRecord = Field(description="Current hosted-game directory state.")
    connection: HostedGameConnection = Field(description="Fresh runtime attachment.")


class ReconnectHostedGameRequest(GatewayModel):
    """Open a player's existing seat using durable principal ownership."""

    principal_id: UUID = Field(description="Principal reconnecting to the seat.")
    principal_capability: str = Field(min_length=32, description="Client credential for the principal.")
    membership_id: UUID = Field(description="Owned game membership to reconnect.")
    client_kind: ClientKind = Field(default=ClientKind.NEUROCLIENT, description="Kind of reconnecting client.")
    client_instance_id: str = Field(min_length=1, max_length=160, description="Browser or process instance identity.")
    attachment_policy: AttachmentPolicy = Field(
        default=AttachmentPolicy.REPLACE_EXISTING,
        description="Whether existing seat attachments remain authorized.",
    )


class ReconnectHostedGameResponse(GatewayModel):
    """Fresh connection plus any attachments displaced by a control move."""

    game: GameRecord = Field(description="Current hosted game record.")
    connection: HostedGameConnection = Field(description="Fresh runtime connection.")
    replaced_attachment_ids: list[UUID] = Field(description="Attachments revoked before reconnecting.")


class StopHostedGameResponse(GatewayModel):
    """Result of administratively stopping one hosted game."""

    game: GameRecord = Field(description="Updated durable game record.")
    stopped: bool = Field(description="Whether a live worker was stopped.")


class StopHostedGameRequest(GatewayModel):
    """Authenticate an administrative hosted-game stop."""

    principal_id: UUID = Field(description="Principal requesting the stop.")
    principal_capability: str = Field(min_length=32, description="Principal identity capability.")


class ObserveHostedGameRequest(GatewayModel):
    """Attach a principal as a new observer under the game's observer policy."""

    principal_id: UUID = Field(description="Principal requesting observer access.")
    principal_capability: str = Field(min_length=32, description="Principal identity capability.")
    client_kind: ClientKind = Field(
        default=ClientKind.NEUROCLIENT,
        description="Kind of observer client.",
    )
    client_instance_id: str = Field(min_length=1, max_length=160, description="Client instance identity.")


class ObserveHostedGameResponse(GatewayModel):
    """Observer connection plus a durable reconnect capability."""

    game: GameRecord = Field(description="Observed game directory record.")
    connection: HostedGameConnection = Field(description="Fresh observer runtime connection.")
    reconnect_grant_id: UUID = Field(description="Durable reconnect-grant identity.")
    reconnect_capability: str = Field(description="Reconnect capability returned once.")
