"""Typed cold-handshake client for remotely executing AI controllers."""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

import httpx

from server.game_directory.contracts import ClientKind
from server.game_gateway_models import (
    AttachHostedGameRequest,
    AttachHostedGameResponse,
    HostedGameConnection,
)


class RemoteAttachmentTransport(Protocol):
    """Minimal HTTP transport required to redeem an agent grant."""

    def post(self, url: str, *, json: object) -> httpx.Response:
        """Post one typed attachment request."""
        ...


def redeem_remote_agent_grant(
    *,
    gateway_url: str,
    game_id: UUID,
    grant_id: UUID,
    grant_capability: str,
    client_instance_id: str,
    client: RemoteAttachmentTransport | None = None,
) -> HostedGameConnection:
    """Redeem a durable grant for one fresh, hot remote-agent connection.

    Args:
        gateway_url: Public multi-game gateway origin.
        game_id: Hosted game receiving the remote process.
        grant_id: Agent attachment grant issued by the game's administrator.
        grant_capability: One-time secret paired with the grant identifier.
        client_instance_id: Stable identity for this policy process instance.
        client: Optional injected HTTP transport used by tests or host apps.

    Returns:
        A game-scoped runtime URL, session, bearer capability, controlled
        entities, and controller lease identifiers.

    Raises:
        httpx.HTTPStatusError: If the gateway rejects the attachment.
        ValueError: If the gateway returns a non-agent connection.
    """
    request = AttachHostedGameRequest(
        grant_id=grant_id,
        capability=grant_capability,
        client_kind=ClientKind.EXTERNAL_AI,
        client_instance_id=client_instance_id,
    )
    owns_client = client is None
    transport: RemoteAttachmentTransport = client or httpx.Client(
        base_url=gateway_url.rstrip("/"),
        timeout=httpx.Timeout(10.0),
    )
    try:
        response = transport.post(
            f"/games/{game_id}/attachments",
            json=request.model_dump(mode="json"),
        )
        response.raise_for_status()
        attachment = AttachHostedGameResponse.model_validate(response.json())
    finally:
        if owns_client:
            assert isinstance(transport, httpx.Client)
            transport.close()
    if attachment.connection.game_id != game_id:
        raise ValueError("Gateway returned an attachment for another game")
    if attachment.connection.access_mode != "agent":
        raise ValueError("Gateway grant did not produce remote-agent authority")
    return attachment.connection
