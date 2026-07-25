"""Structured, bounded instrumentation owned by the native AI runtime."""

from __future__ import annotations

from collections import deque
from enum import Enum
import threading
import time
from types import TracebackType
from typing import Callable, Literal, Mapping, Protocol

from pydantic import BaseModel, ConfigDict, Field

from dnd.ai.policy import PolicyDescriptor


class AIExecutionPhase(str, Enum):
    """Canonical phases measured outside policy implementations."""

    ASSIGNMENT_INITIALIZATION = "assignment_initialization"
    POLICY_CONSTRUCTION = "policy_construction"
    MEMORY_CONSTRUCTION = "memory_construction"
    DECISION_TOTAL = "decision_total"
    STATE_PROJECTION = "state_projection"
    MEMORY_REDUCTION = "memory_reduction"
    POLICY_DECISION = "policy_decision"
    DECISION_VALIDATION = "decision_validation"
    ACTION_EXECUTION = "action_execution"
    FEEDBACK_REDUCTION = "feedback_reduction"
    PROVIDER_HANDSHAKE_WAIT = "provider_handshake_wait"
    PROVIDER_ASSIGNMENT_OPEN_WAIT = "provider_assignment_open_wait"
    PROVIDER_DECISION_WAIT = "provider_decision_wait"
    PROVIDER_ASSIGNMENT_CLOSE_WAIT = "provider_assignment_close_wait"
    ASSIGNMENT_TEARDOWN = "assignment_teardown"


class AIInstrumentationContext(BaseModel):
    """Correlation identity shared by every phase of one decision."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    game_id: str = Field(min_length=1)
    assignment_id: str = Field(min_length=1)
    actor_uuid: str = Field(min_length=1)
    decision_id: str = Field(min_length=1)
    policy: PolicyDescriptor


class AIPhaseTiming(BaseModel):
    """Completed wall and current-thread CPU duration for one phase."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    sequence: int = Field(ge=1)
    context: AIInstrumentationContext
    phase: AIExecutionPhase
    wall_duration_ns: int = Field(ge=0)
    thread_cpu_duration_ns: int = Field(ge=0)
    succeeded: bool
    error_type: str | None = None


class AITraceEvent(BaseModel):
    """Bounded structured runtime event without arbitrary policy logging."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    sequence: int = Field(ge=1)
    context: AIInstrumentationContext
    event: str = Field(min_length=1)
    attributes: tuple[tuple[str, str], ...] = ()


class AIInstrumentationSink(Protocol):
    """Destination for structured timing and trace records."""

    def record_timing(self, timing: AIPhaseTiming) -> None:
        """Store or export one completed phase timing."""
        ...

    def record_event(self, event: AITraceEvent) -> None:
        """Store or export one bounded trace event."""
        ...


class NullAIInstrumentationSink:
    """Zero-retention sink used when no diagnostics consumer is installed."""

    def record_timing(self, timing: AIPhaseTiming) -> None:
        del timing

    def record_event(self, event: AITraceEvent) -> None:
        del event


class BoundedAIInstrumentationSink:
    """Thread-safe bounded sink suitable for local diagnostics and tests."""

    def __init__(
        self,
        *,
        maximum_timings: int = 2048,
        maximum_events: int = 512,
    ) -> None:
        if maximum_timings < 1:
            raise ValueError("maximum_timings must be positive")
        if maximum_events < 1:
            raise ValueError("maximum_events must be positive")
        self._timings: deque[AIPhaseTiming] = deque(maxlen=maximum_timings)
        self._events: deque[AITraceEvent] = deque(maxlen=maximum_events)
        self._lock = threading.Lock()

    def record_timing(self, timing: AIPhaseTiming) -> None:
        with self._lock:
            self._timings.append(timing)

    def record_event(self, event: AITraceEvent) -> None:
        with self._lock:
            self._events.append(event)

    def timing_snapshot(self) -> tuple[AIPhaseTiming, ...]:
        """Return a stable copy of retained timings."""
        with self._lock:
            return tuple(self._timings)

    def event_snapshot(self) -> tuple[AITraceEvent, ...]:
        """Return a stable copy of retained trace events."""
        with self._lock:
            return tuple(self._events)


class AIInstrumentation:
    """Own clocks, record ordering, and trace bounds for an AI runtime."""

    def __init__(
        self,
        *,
        sink: AIInstrumentationSink | None = None,
        wall_clock_ns: Callable[[], int] = time.perf_counter_ns,
        thread_cpu_clock_ns: Callable[[], int] = time.thread_time_ns,
        maximum_event_attributes: int = 16,
        maximum_attribute_length: int = 256,
    ) -> None:
        if maximum_event_attributes < 1:
            raise ValueError("maximum_event_attributes must be positive")
        if maximum_attribute_length < 1:
            raise ValueError("maximum_attribute_length must be positive")
        self._sink = sink or NullAIInstrumentationSink()
        self._wall_clock_ns = wall_clock_ns
        self._thread_cpu_clock_ns = thread_cpu_clock_ns
        self._maximum_event_attributes = maximum_event_attributes
        self._maximum_attribute_length = maximum_attribute_length
        self._sequence = 0
        self._sequence_lock = threading.Lock()

    def measure(
        self,
        *,
        context: AIInstrumentationContext,
        phase: AIExecutionPhase,
    ) -> "_AIPhaseMeasurement":
        """Create one phase scope that records success or failure on exit."""
        return _AIPhaseMeasurement(
            instrumentation=self,
            context=context,
            phase=phase,
        )

    def emit_event(
        self,
        *,
        context: AIInstrumentationContext,
        event: str,
        attributes: Mapping[str, object] | None = None,
    ) -> None:
        """Emit one bounded structured event without invoking a logger."""
        if not event:
            raise ValueError("AI trace event name must not be empty")
        raw_attributes = attributes or {}
        bounded = tuple(
            (
                str(key)[: self._maximum_attribute_length],
                str(value)[: self._maximum_attribute_length],
            )
            for key, value in sorted(
                raw_attributes.items(),
                key=lambda item: str(item[0]),
            )[: self._maximum_event_attributes]
        )
        self._sink.record_event(
            AITraceEvent(
                sequence=self._next_sequence(),
                context=context,
                event=event,
                attributes=bounded,
            )
        )

    def _next_sequence(self) -> int:
        with self._sequence_lock:
            self._sequence += 1
            return self._sequence

    def _record_timing(
        self,
        *,
        context: AIInstrumentationContext,
        phase: AIExecutionPhase,
        wall_started_ns: int,
        thread_cpu_started_ns: int,
        error_type: type[BaseException] | None,
    ) -> None:
        self._sink.record_timing(
            AIPhaseTiming(
                sequence=self._next_sequence(),
                context=context,
                phase=phase,
                wall_duration_ns=max(0, self._wall_clock_ns() - wall_started_ns),
                thread_cpu_duration_ns=max(
                    0,
                    self._thread_cpu_clock_ns() - thread_cpu_started_ns,
                ),
                succeeded=error_type is None,
                error_type=error_type.__name__ if error_type is not None else None,
            )
        )


class _AIPhaseMeasurement:
    """Concrete context manager returned by :meth:`AIInstrumentation.measure`."""

    def __init__(
        self,
        *,
        instrumentation: AIInstrumentation,
        context: AIInstrumentationContext,
        phase: AIExecutionPhase,
    ) -> None:
        self._instrumentation = instrumentation
        self._context = context
        self._phase = phase
        self._wall_started_ns = 0
        self._thread_cpu_started_ns = 0

    def __enter__(self) -> "_AIPhaseMeasurement":
        self._wall_started_ns = self._instrumentation._wall_clock_ns()
        self._thread_cpu_started_ns = (
            self._instrumentation._thread_cpu_clock_ns()
        )
        return self

    def __exit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: TracebackType | None,
    ) -> Literal[False]:
        del exception, traceback
        self._instrumentation._record_timing(
            context=self._context,
            phase=self._phase,
            wall_started_ns=self._wall_started_ns,
            thread_cpu_started_ns=self._thread_cpu_started_ns,
            error_type=exception_type,
        )
        return False
