"""Transport contract for managed agent-service lifecycle handshakes."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


MANAGED_AGENT_READY_ROUTE_TEMPLATE = (
    "/ai/sessions/{session_id}/service-ready"
)


class AgentServiceReadyRequest(BaseModel):
    """One-time proof that a managed agent completed transport bootstrap."""

    model_config = ConfigDict(extra="forbid")

    readiness_token: str = Field(min_length=16, max_length=256)
