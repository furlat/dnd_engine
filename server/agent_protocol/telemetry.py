"""Dependency-neutral contracts for session-scoped agent telemetry."""

from __future__ import annotations

import time
from typing import Any, Dict, List, Literal, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


class AgentEvent(BaseModel):
    """Session-scoped event describing agent runtime or policy behavior."""

    event_id: str = Field(default_factory=lambda: str(uuid4()), description="Unique event id.")
    session_id: str = Field(description="Session UUID.")
    actor_uuid: Optional[str] = Field(default=None, description="Actor UUID associated with the event.")
    epoch_id: Optional[str] = Field(default=None, description="Decision epoch id associated with the event.")
    observation_cursor: Optional[int] = Field(default=None, description="Observation cursor associated with the event.")
    event_type: str = Field(description="Typed agent event name.")
    level: Literal["debug", "info", "warning", "error"] = Field(default="info", description="Event severity.")
    source: str = Field(description="Subsystem or policy that emitted the event.")
    summary: str = Field(description="Concise human-readable summary.")
    payload: Dict[str, Any] = Field(default_factory=dict, description="Structured event payload.")
    tags: List[str] = Field(default_factory=list, description="Search and UI tags.")
    created_at: float = Field(default_factory=time.time, description="Unix timestamp when emitted.")


class PolicySourceManifest(BaseModel):
    """Opaque client-supplied identity and source manifest for one policy."""

    policy_name: str = Field(description="Stable policy identifier.")
    policy_version: str = Field(description="Human-readable policy version label.")
    source_path: str = Field(description="Primary client-relative policy entry point.")
    source_paths: List[str] = Field(description="Ordered client-relative paths in the source manifest.")
    source_sha256: str = Field(description="SHA-256 hash of the exact composite source manifest.")
    line_count: int = Field(description="Number of lines in the composite source manifest.")
    source: str = Field(description="Exact composite policy source manifest.")


class AgentEventPayload(BaseModel):
    """Cursor-addressed agent event envelope."""

    event_index: int = Field(description="Zero-based event index for the session.")
    agent_cursor: int = Field(description="Cursor after this event.")
    observation_cursor: Optional[int] = Field(default=None, description="Paired observation cursor.")
    epoch_id: Optional[str] = Field(default=None, description="Paired epoch id.")
    event: AgentEvent = Field(description="Agent event payload.")


class AgentStreamSyncPayload(BaseModel):
    """Initial cursor state for an agent-event SSE stream."""

    agent_cursor: int = Field(description="Current agent-event cursor.")
    observation_cursor: Optional[int] = Field(default=None, description="Current observation cursor when known.")
    epoch_id: Optional[str] = Field(default=None, description="Current epoch id when known.")
    session: Optional[Dict[str, Any]] = Field(default=None, description="Optional session status.")


class AgentHeartbeatPayload(BaseModel):
    """Keepalive payload for an agent-event SSE stream."""

    server_time: float = Field(description="Server timestamp.")
    agent_cursor: int = Field(description="Current agent-event cursor.")
    observation_cursor: Optional[int] = Field(default=None, description="Current observation cursor when known.")
    epoch_id: Optional[str] = Field(default=None, description="Current epoch id when known.")
    session: Optional[Dict[str, Any]] = Field(default=None, description="Optional session status.")


class AgentEventIngestRequest(BaseModel):
    """Batch of agent telemetry events posted by a local runtime."""

    events: List[AgentEvent] = Field(description="Agent events to append to the session stream.")


class AgentEventHistoryResponse(BaseModel):
    """Cursor-addressed history of agent telemetry events."""

    events: List[AgentEventPayload] = Field(description="Agent events after the requested cursor.")
    count: int = Field(description="Number of returned events.")
    total: int = Field(description="Current session event cursor.")
    next_agent_cursor: int = Field(description="Cursor after the final returned event, or the requested cursor when empty.")
    earliest_agent_cursor: int = Field(description="First retained event cursor available for replay.")
    resync_required: bool = Field(description="Whether the requested cursor predates retained history.")
