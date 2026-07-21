"""Pydantic contracts for the agent-side subjective runtime."""

from __future__ import annotations

import time
from typing import Any, Dict, List, Literal, Optional
from uuid import uuid4

from pydantic import BaseModel, Field

from ai.knowledge.models import AgentFacts


class BriefEmission(BaseModel):
    """Text and data emitted for humans or LLM agents."""

    title: str = Field(description="Brief title.")
    text: str = Field(description="Rendered brief text.")
    data: Dict[str, Any] = Field(default_factory=dict, description="Structured brief data.")


class Alert(BaseModel):
    """Important runtime or tactical alert."""

    level: Literal["info", "warning", "error"] = Field(description="Alert severity.")
    message: str = Field(description="Human-readable alert.")
    data: Dict[str, Any] = Field(default_factory=dict, description="Structured alert data.")


class PolicyHint(BaseModel):
    """Non-binding recommendation for downstream policy code."""

    name: str = Field(description="Hint name.")
    row_id: Optional[str] = Field(default=None, description="Suggested row id, if any.")
    reason: str = Field(description="Why this hint was produced.")
    score: float = Field(default=0.0, description="Relative hint score.")


class TraceEmission(BaseModel):
    """Structured trace emitted by runtime or processors."""

    event: str = Field(description="Trace event name.")
    data: Dict[str, Any] = Field(default_factory=dict, description="Trace data.")


class AgentState(BaseModel):
    """Derived policy workspace built from subjective world and affordances."""

    facts: Optional[AgentFacts] = Field(default=None, description="Typed policy facts for the current world revision.")
    variables: Dict[str, Any] = Field(default_factory=dict, description="Named derived variables.")
    briefs: List[BriefEmission] = Field(default_factory=list, description="Recent emitted briefs.")
    alerts: List[Alert] = Field(default_factory=list, description="Active alerts.")
    hints: List[PolicyHint] = Field(default_factory=list, description="Policy hints.")
    trace: List[TraceEmission] = Field(default_factory=list, description="Runtime trace entries.")


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
