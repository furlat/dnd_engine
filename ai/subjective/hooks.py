"""Hook pipeline for subjective runtime post-processors."""

from __future__ import annotations

from enum import Enum
import time
from typing import Protocol

from pydantic import BaseModel, Field

from ai.knowledge.models import AgentFacts
from ai.observation.models import SubjectiveWorldState
from ai.subjective.models import AgentState, Alert, BriefEmission, PolicyHint, TraceEmission

MAX_AGENT_STATE_HISTORY = 20


class HookPoint(str, Enum):
    """Lifecycle hook point emitted by the subjective runtime."""

    BOOTSTRAP = "on_bootstrap"
    SNAPSHOT_LOADED = "on_snapshot_loaded"
    FRAME_APPLIED = "on_frame_applied"
    EPOCH_STARTED = "on_epoch_started"
    ACTION_COMPLETED = "on_action_completed"
    ACTION_INTERRUPTED = "on_action_interrupted"
    ACTION_CANCELED = "on_action_canceled"
    ACTION_REJECTED = "on_action_rejected"
    ACTION_STALE = "on_action_stale"
    STREAM_GAP = "on_stream_gap"
    RESYNC_COMPLETED = "on_resync_completed"


class DerivedVariableUpdate(BaseModel):
    """Set or replace a derived variable in AgentState."""

    name: str = Field(description="Variable name.")
    value: object = Field(description="Variable value.")


class DerivedVariableDelete(BaseModel):
    """Delete a derived variable from AgentState."""

    name: str = Field(description="Variable name.")


class ProcessorOutput(BaseModel):
    """Single output from a post-processor."""

    facts_update: AgentFacts | None = Field(default=None, description="Typed policy fact replacement.")
    variable_update: DerivedVariableUpdate | None = Field(default=None, description="Variable update.")
    variable_delete: DerivedVariableDelete | None = Field(default=None, description="Variable deletion.")
    brief: BriefEmission | None = Field(default=None, description="Brief emission.")
    alert: Alert | None = Field(default=None, description="Alert emission.")
    hint: PolicyHint | None = Field(default=None, description="Policy hint.")
    trace: TraceEmission | None = Field(default=None, description="Trace emission.")


class HookContext(BaseModel):
    """Context passed to post-processors."""

    hook: HookPoint = Field(description="Hook point.")
    world: SubjectiveWorldState = Field(description="Current world state.")
    agent_state: AgentState = Field(description="Current agent state.")
    previous_world: SubjectiveWorldState | None = Field(default=None, description="World state before the hook, if any.")


class PostProcessor(Protocol):
    """Protocol implemented by subjective runtime post-processors."""

    name: str
    order: int

    def run(self, context: HookContext) -> list[ProcessorOutput]:
        """Run the processor for one hook context."""
        ...


class HookRegistry:
    """Deterministic post-processor registry."""

    def __init__(self, processors: list[PostProcessor] | None = None) -> None:
        """Create a registry.

        Args:
            processors: Initial processors.
        """
        self.processors = sorted(processors or [], key=lambda processor: (processor.order, processor.name))
        self.last_timings_ms: dict[str, float] = {}

    def run(self, context: HookContext) -> AgentState:
        """Run all processors and apply their outputs to AgentState."""
        state_started = time.perf_counter()
        state = context.agent_state.model_copy(
            update={
                "facts": context.agent_state.facts,
                "variables": dict(context.agent_state.variables),
                "briefs": list(context.agent_state.briefs[-MAX_AGENT_STATE_HISTORY:]),
                "alerts": list(context.agent_state.alerts[-MAX_AGENT_STATE_HISTORY:]),
                "hints": list(context.agent_state.hints[-MAX_AGENT_STATE_HISTORY:]),
                "trace": list(context.agent_state.trace[-MAX_AGENT_STATE_HISTORY:]),
            },
            deep=False,
        )
        timings = {
            "state_copy": (time.perf_counter() - state_started) * 1000.0,
        }
        for processor in self.processors:
            should_run = getattr(processor, "should_run", None)
            if callable(should_run) and not should_run(context):
                continue
            hook_points = getattr(processor, "hook_points", None)
            if hook_points is not None and context.hook not in hook_points:
                continue
            processor_started = time.perf_counter()
            processor_context = context.model_copy(update={"agent_state": state})
            for output in processor.run(processor_context):
                _apply_output(state, output)
            timings[processor.name] = (time.perf_counter() - processor_started) * 1000.0
        trim_started = time.perf_counter()
        _trim_state_history(state)
        timings["state_trim"] = (time.perf_counter() - trim_started) * 1000.0
        self.last_timings_ms = timings
        return state


def _apply_output(state: AgentState, output: ProcessorOutput) -> None:
    """Apply one processor output to mutable AgentState."""
    if output.facts_update is not None:
        state.facts = output.facts_update
    if output.variable_update is not None:
        state.variables[output.variable_update.name] = output.variable_update.value
    if output.variable_delete is not None:
        state.variables.pop(output.variable_delete.name, None)
    if output.brief is not None:
        state.briefs.append(output.brief)
    if output.alert is not None:
        state.alerts.append(output.alert)
    if output.hint is not None:
        state.hints.append(output.hint)
    if output.trace is not None:
        state.trace.append(output.trace)


def _trim_state_history(state: AgentState) -> None:
    """Bound append-only derived state lists used for local runtime context."""
    del state.briefs[:-MAX_AGENT_STATE_HISTORY]
    del state.alerts[:-MAX_AGENT_STATE_HISTORY]
    del state.hints[:-MAX_AGENT_STATE_HISTORY]
    del state.trace[:-MAX_AGENT_STATE_HISTORY]
