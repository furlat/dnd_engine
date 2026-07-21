"""Typed takeover transport contracts for the persistent Codex runtime."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class ToolError(BaseModel):
    """Structured error returned by Codex takeover transport."""

    code: str = Field(description="Machine-readable error code.")
    message: str = Field(description="Human-readable error message.")
    status_code: Optional[int] = Field(default=None, description="HTTP status code when applicable.")
    detail: Any = Field(default=None, description="Original error detail when available.")


class TakeoverEntityInfo(BaseModel):
    """Typed entity ownership row carried by a takeover claim."""

    entity_uuid: str = Field(description="Claimed entity UUID.")
    entity_name: str = Field(description="Claimed entity display name.")
    faction: Optional[str] = Field(default=None, description="Claimed entity faction when known.")
    previous_controller_uuid: str = Field(description="Controller UUID restored when the claim is released.")
    previous_controller_type: Optional[str] = Field(
        default=None,
        description="Controller type active before the takeover.",
    )
    current_controller_type: Optional[str] = Field(
        default=None,
        description="Controller type currently assigned to the entity.",
    )
    previous_owner_session_id: Optional[str] = Field(
        default=None,
        description="Session that owned the entity before the takeover.",
    )


class TakeoverClaimInfo(BaseModel):
    """Typed takeover identity used to create or adopt controller ownership."""

    claim_id: str = Field(description="Takeover claim UUID.")
    session_id: str = Field(description="Codex session UUID controlling the claim.")
    name: str = Field(description="Claim display name.")
    faction: Optional[str] = Field(default=None, description="Faction claimed when faction-based.")
    created_at: float = Field(description="Unix timestamp when the claim was created.")
    last_heartbeat_at: float = Field(description="Unix timestamp of the latest heartbeat.")
    lease_seconds: float = Field(gt=0, description="Lease duration in seconds.")
    expires_at: float = Field(description="Unix timestamp when the claim expires.")
    is_expired: bool = Field(description="Whether the server considers the claim expired.")
    claimed_entities: list[TakeoverEntityInfo] = Field(description="Entities controlled by the claim.")


class TakeoverHeartbeatResult(BaseModel):
    """Typed response returned when an existing takeover lease is renewed."""

    status: str = Field(description="Heartbeat operation status.")
    claim: TakeoverClaimInfo = Field(description="Authoritative renewed claim.")
