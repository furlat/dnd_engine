"""Pydantic contracts for the agent-side subjective runtime."""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

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
