"""HTTP/SSE runtime client for subjective AI controllers."""

from __future__ import annotations

import gc
import json
import logging
import socket
from threading import Condition, Event as ThreadEvent, RLock, Thread
import time
from dataclasses import dataclass, field
from typing import Any, Iterator, Optional, Protocol
from uuid import uuid4

import httpx

from ai.ordered_delivery import OrderedDeliveryWorker
from dnd.ai.contracts.observation import ObservationFrame, ObservationFrameType, ObservationSnapshot
from ai.policy.contracts import PolicyDecisionTelemetry
from dnd.ai.contracts.control import (
    ActionResolutionStatus,
    CommandResult,
    CommandResultStatus,
    DecisionEpoch,
    END_TURN_ROW_ID,
)
from ai.subjective.hooks import HookContext, HookPoint, HookRegistry
from server.agent_protocol.telemetry import AgentEvent
from ai.subjective.processors import default_processors
from ai.subjective.queries import SubjectiveQueries
from dnd.ai.runtime_gc import (
    RuntimeGcPolicy,
    SUSPEND_AUTOMATIC_GC,
    automatic_gc_suspended,
)
from ai.subjective.store import ApplyResultKind, SubjectiveStore

logger = logging.getLogger(__name__)
DEFAULT_CONTROL_REQUEST_TIMEOUT_SECONDS = 10.0
DEFAULT_RUNTIME_CLOSE_TIMEOUT_SECONDS = 4.0


class SubjectiveEncounterEndedError(RuntimeError):
    """Raised when an epoch wait reaches a terminal subjective encounter."""


class SubjectiveRuntimeClosedError(RuntimeError):
    """Raised when cooperative runtime shutdown interrupts a pending operation."""


class SubjectiveObservationGapError(RuntimeError):
    """Raised internally when the live stream skips an observation cursor."""


class SubjectiveEvidenceRecorder(Protocol):
    """Durable observer for the exact subjective inputs consumed by a runtime."""

    def record_snapshot(self, snapshot: ObservationSnapshot, *, reason: str) -> None:
        """Retain one bootstrap or recovery snapshot."""
        ...

    def record_frame(self, frame: ObservationFrame) -> None:
        """Retain one newly applied subjective event envelope."""
        ...

    def record_agent_event(self, event: AgentEvent) -> None:
        """Retain one local runtime telemetry event."""
        ...

    def record_command_intent(self, payload: dict[str, Any]) -> None:
        """Retain command intent before network submission."""
        ...

    def record_command_acknowledgement(self, result: CommandResult) -> None:
        """Retain the validated controller acknowledgement."""
        ...

    def record_command_transport_failure(self, command_id: str, error: BaseException) -> None:
        """Retain an ambiguous transport failure without claiming a game outcome."""
        ...


def _gc_collection_counts() -> tuple[int, int, int]:
    """Return completed cyclic-GC collections by generation."""
    stats = gc.get_stats()
    return (
        int(stats[0]["collections"]),
        int(stats[1]["collections"]),
        int(stats[2]["collections"]),
    )


@dataclass
class CommandTimingProbe:
    """Low-overhead timing probe for one subjective command."""

    command_type: str
    command_id: str = ""
    actor_uuid: Optional[str] = None
    epoch_id: Optional[str] = None
    row_id: Optional[str] = None
    status: Optional[str] = None
    resync_required: bool = False
    started_at: float = field(default_factory=time.perf_counter)
    wait_for_epoch_ms: float = 0.0
    submit_http_ms: float = 0.0
    ack_parse_ms: float = 0.0
    sse_wait_ms: float = 0.0
    sse_events: int = 0
    sse_frames: int = 0
    sse_sync_events: int = 0
    sse_evicted_events: int = 0
    stream_reduction_ms: float = 0.0
    stream_frame_parse_ms: float = 0.0
    stream_store_apply_ms: float = 0.0
    stream_hook_ms: float = 0.0
    stream_processor_ms: dict[str, float] = field(default_factory=dict)
    resync_ms: float = 0.0
    server_timing: Optional[dict[str, Any]] = None
    gc_collections_started: tuple[int, int, int] = field(
        default_factory=_gc_collection_counts
    )

    def elapsed_ms(self) -> float:
        """Return total elapsed milliseconds."""
        return _elapsed_ms(self.started_at)

    def model_dump(self) -> dict[str, Any]:
        """Return JSON-friendly timing fields."""
        current_gc_collections = _gc_collection_counts()
        return {
            "command_type": self.command_type,
            "command_id": self.command_id,
            "actor_uuid": self.actor_uuid,
            "epoch_id": self.epoch_id,
            "row_id": self.row_id,
            "status": self.status,
            "resync_required": self.resync_required,
            "total_ms": self.elapsed_ms(),
            "wait_for_epoch_ms": _round_ms(self.wait_for_epoch_ms),
            "submit_http_ms": _round_ms(self.submit_http_ms),
            "ack_parse_ms": _round_ms(self.ack_parse_ms),
            "sse_wait_ms": _round_ms(self.sse_wait_ms),
            "sse_events": self.sse_events,
            "sse_frames": self.sse_frames,
            "sse_sync_events": self.sse_sync_events,
            "sse_evicted_events": self.sse_evicted_events,
            "stream_reduction_ms": _round_ms(self.stream_reduction_ms),
            "stream_frame_parse_ms": _round_ms(self.stream_frame_parse_ms),
            "stream_store_apply_ms": _round_ms(self.stream_store_apply_ms),
            "stream_hook_ms": _round_ms(self.stream_hook_ms),
            "stream_processor_ms": {
                name: _round_ms(elapsed_ms)
                for name, elapsed_ms in self.stream_processor_ms.items()
            },
            "automatic_gc_suspended": automatic_gc_suspended(),
            "gc_collections_during_command": [
                current - started
                for current, started in zip(
                    current_gc_collections,
                    self.gc_collections_started,
                )
            ],
            "resync_ms": _round_ms(self.resync_ms),
            "server_timing": self.server_timing,
        }


@dataclass
class _DeferredFrameEffects:
    """Frame side effects deferred during command follow-up catch-up."""

    previous_world: Any = None
    applied: bool = False
    command_result_frames: list[ObservationFrame] = field(default_factory=list)
    epoch_started_frames: list[ObservationFrame] = field(default_factory=list)
    epoch_cleared_frames: list[ObservationFrame] = field(default_factory=list)

    def record(self, frame: ObservationFrame, previous_world: Any) -> None:
        """Record a frame whose store mutation has already been applied."""
        if not self.applied:
            self.previous_world = previous_world
        self.applied = True
        if frame.command_result is not None:
            self.command_result_frames.append(frame)
        if frame.frame_type == ObservationFrameType.DECISION_EPOCH and frame.decision_epoch is not None:
            self.epoch_started_frames.append(frame)
        elif frame.frame_type == ObservationFrameType.DECISION_EPOCH:
            self.epoch_cleared_frames.append(frame)


@dataclass(frozen=True)
class _CommandStreamBaseline:
    """Cumulative stream counters captured before one command submission."""

    events: int
    frames: int
    syncs: int
    evictions: int
    reduction_ms: float
    frame_parse_ms: float
    store_apply_ms: float
    hook_ms: float
    resync_generation: int
    processor_ms: dict[str, float]


class AgentEventSink(Protocol):
    """Destination for agent events."""

    def emit(self, event: AgentEvent) -> None:
        """Emit one event."""
        ...

    def emit_many(self, events: list[AgentEvent]) -> None:
        """Emit several events."""
        ...


class MemoryAgentEventSink:
    """In-memory agent event sink for tests."""

    def __init__(self) -> None:
        self.events: list[AgentEvent] = []

    def emit(self, event: AgentEvent) -> None:
        self.events.append(event)

    def emit_many(self, events: list[AgentEvent]) -> None:
        self.events.extend(events)


class LoggingAgentEventSink:
    """Structured logging sink for agent events."""

    def emit(self, event: AgentEvent) -> None:
        logger.info("agent_event %s", event.model_dump_json())

    def emit_many(self, events: list[AgentEvent]) -> None:
        for event in events:
            self.emit(event)


class HttpAgentEventSink:
    """HTTP sink posting agent events to the server."""

    def __init__(self, client: httpx.Client, session_id: str) -> None:
        self.client = client
        self.session_id = session_id

    def emit(self, event: AgentEvent) -> None:
        self.emit_many([event])

    def emit_many(self, events: list[AgentEvent]) -> None:
        if not events:
            return
        payload = {"events": [event.model_dump(mode="json") for event in events]}
        try:
            response = self.client.post(f"/ai/sessions/{self.session_id}/agent-events", json=payload)
            response.raise_for_status()
        except httpx.HTTPError:
            logger.exception("failed to post agent events")


class CompositeAgentEventSink:
    """Fan-out sink for agent events."""

    def __init__(self, sinks: list[AgentEventSink]) -> None:
        self.sinks = sinks

    def emit(self, event: AgentEvent) -> None:
        for sink in self.sinks:
            sink.emit(event)

    def emit_many(self, events: list[AgentEvent]) -> None:
        for sink in self.sinks:
            sink.emit_many(events)


class QueuedAgentEventSink:
    """Deliver ordered agent telemetry without blocking gameplay reduction."""

    def __init__(
        self,
        destination: AgentEventSink,
        *,
        max_depth: int = 1024,
        session_id: Optional[str] = None,
    ) -> None:
        """Create one bounded telemetry delivery worker.

        Args:
            destination: Synchronous sink owned by the worker thread.
            max_depth: Maximum number of pending event batches.
        """
        if max_depth < 1:
            raise ValueError("max_depth must be positive")
        self.destination = destination
        worker_session_id = session_id or str(
            getattr(destination, "session_id", "unscoped")
        )
        self._delivery = OrderedDeliveryWorker(
            destination.emit_many,
            name=f"agent-events-{worker_session_id}",
            max_depth=max_depth,
        )

    def emit(self, event: AgentEvent) -> None:
        """Enqueue one immutable event in source order."""
        self.emit_many([event])

    def emit_many(self, events: list[AgentEvent]) -> None:
        """Enqueue one ordered event batch."""
        if events:
            self._delivery.submit(list(events))

    def flush(
        self,
        timeout_seconds: float = DEFAULT_RUNTIME_CLOSE_TIMEOUT_SECONDS,
    ) -> None:
        """Wait until every previously queued event is delivered."""
        self._delivery.flush(timeout_seconds)

    def close(
        self,
        timeout_seconds: float = DEFAULT_RUNTIME_CLOSE_TIMEOUT_SECONDS,
    ) -> None:
        """Flush and stop the delivery worker exactly once."""
        self._delivery.close(timeout_seconds)

    @property
    def worker_alive(self) -> bool:
        """Return whether the delivery worker remains alive."""
        return self._delivery.worker_alive


class SubjectiveRuntime:
    """Long-lived local runtime for one AI session."""

    def __init__(
        self,
        base_url: str,
        session_id: str,
        *,
        event_sink: Optional[AgentEventSink] = None,
        evidence_recorder: Optional[SubjectiveEvidenceRecorder] = None,
        processors: Optional[list] = None,
        command_followup_timeout: float = 10.0,
        include_command_diagnostics: bool = False,
        unix_socket_path: Optional[str] = None,
        runtime_token: Optional[str] = None,
        gc_policy: RuntimeGcPolicy = SUSPEND_AUTOMATIC_GC,
        control_request_timeout: float = DEFAULT_CONTROL_REQUEST_TIMEOUT_SECONDS,
    ) -> None:
        """Create a runtime client."""
        if control_request_timeout <= 0:
            raise ValueError("control_request_timeout must be positive")
        self.base_url = base_url.rstrip("/")
        self.session_id = session_id
        transport = httpx.HTTPTransport(uds=unix_socket_path) if unix_socket_path else None
        stream_transport = httpx.HTTPTransport(uds=unix_socket_path) if unix_socket_path else None
        transport_base_url = "http://game-worker" if unix_socket_path else self.base_url
        headers = (
            {"Authorization": f"Bearer {runtime_token}"}
            if runtime_token is not None
            else None
        )
        self.client = httpx.Client(
            base_url=transport_base_url,
            timeout=httpx.Timeout(
                connect=control_request_timeout,
                read=control_request_timeout,
                write=control_request_timeout,
                pool=control_request_timeout,
            ),
            transport=transport,
            headers=headers,
        )
        self.stream_client = httpx.Client(
            base_url=transport_base_url,
            timeout=httpx.Timeout(connect=5.0, read=None, write=10.0, pool=5.0),
            transport=stream_transport,
            headers=headers,
        )
        self._telemetry_client: Optional[httpx.Client] = None
        self.store = SubjectiveStore()
        self.state_lock = RLock()
        self._cleanup_lock = RLock()
        self._state_changed = Condition(self.state_lock)
        self._stream_stop = ThreadEvent()
        self._stream_ready = ThreadEvent()
        self._stream_thread: Optional[Thread] = None
        self._active_stream_response: Optional[httpx.Response] = None
        self._stream_error: Optional[BaseException] = None
        self._stream_event_count = 0
        self._stream_frame_count = 0
        self._stream_sync_count = 0
        self._stream_evicted_count = 0
        self._stream_reduction_ms = 0.0
        self._stream_frame_parse_ms = 0.0
        self._stream_store_apply_ms = 0.0
        self._stream_hook_ms = 0.0
        self._stream_processor_ms: dict[str, float] = {}
        self._resync_generation = 0
        self._command_stream_baselines: dict[str, _CommandStreamBaseline] = {}
        self._closed = False
        self._resources_closed = False
        self.command_followup_timeout = command_followup_timeout
        self.include_command_diagnostics = include_command_diagnostics
        self.hooks = HookRegistry(processors if processors is not None else default_processors())
        self.evidence_recorder = evidence_recorder
        if event_sink is None:
            # Cooperative stop must be able to interrupt control and SSE reads
            # without invalidating telemetry that the FIFO worker already owns.
            telemetry_transport = (
                httpx.HTTPTransport(uds=unix_socket_path)
                if unix_socket_path
                else None
            )
            self._telemetry_client = httpx.Client(
                base_url=transport_base_url,
                timeout=httpx.Timeout(
                    connect=control_request_timeout,
                    read=control_request_timeout,
                    write=control_request_timeout,
                    pool=control_request_timeout,
                ),
                transport=telemetry_transport,
                headers=headers,
            )
            self.event_sink = QueuedAgentEventSink(
                CompositeAgentEventSink([
                    LoggingAgentEventSink(),
                    HttpAgentEventSink(self._telemetry_client, session_id),
                ]),
                session_id=session_id,
            )
        else:
            self.event_sink = event_sink
        self.last_command_timing: Optional[dict[str, Any]] = None
        self._gc_lease = gc_policy.acquire()

    @property
    def query(self) -> SubjectiveQueries:
        """Return local query facade."""
        with self.state_lock:
            if self.store.world is None:
                raise RuntimeError("SubjectiveRuntime.bootstrap() must be called before query access.")
            return SubjectiveQueries(self.store.world, self.store.agent_state)

    def request_close(self) -> None:
        """Wake cooperative waiters without blocking the requesting thread."""
        with self._state_changed:
            if self._closed:
                return
            self._closed = True
            self._stream_stop.set()
            self._stream_ready.set()
            self._state_changed.notify_all()
            active_stream_response = self._active_stream_response
        if active_stream_response is not None:
            try:
                _interrupt_httpx_response_read(active_stream_response)
            except Exception:
                logger.exception(
                    "failed to interrupt subjective observation stream for session %s",
                    self.session_id,
                )
        for client in (self.stream_client, self.client):
            try:
                client.close()
            except Exception:
                logger.exception(
                    "failed to interrupt subjective runtime transport for session %s",
                    self.session_id,
                )

    def close(
        self,
        timeout_seconds: float = DEFAULT_RUNTIME_CLOSE_TIMEOUT_SECONDS,
    ) -> None:
        """Close every runtime resource within one aggregate deadline."""
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        self.request_close()
        deadline = time.monotonic() + timeout_seconds
        with self._cleanup_lock:
            with self._state_changed:
                if self._resources_closed:
                    return
                stream_thread = self._stream_thread
            failures: list[BaseException] = []
            for client in (self.stream_client, self.client):
                try:
                    client.close()
                except BaseException as exc:
                    failures.append(exc)
            if stream_thread is not None and stream_thread.is_alive():
                remaining = max(0.0, deadline - time.monotonic())
                stream_thread.join(timeout=remaining)
                if stream_thread.is_alive():
                    failures.append(TimeoutError(
                        "subjective observation worker did not stop for session "
                        f"{self.session_id}"
                    ))
            close_sink = getattr(self.event_sink, "close", None)
            telemetry_sink_closed = not callable(close_sink)
            if callable(close_sink):
                try:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise TimeoutError(
                            "runtime telemetry cleanup exhausted its deadline"
                        )
                    if isinstance(self.event_sink, QueuedAgentEventSink):
                        self.event_sink.close(remaining)
                    else:
                        close_sink()
                    telemetry_sink_closed = True
                except BaseException as exc:
                    failures.append(exc)
            if telemetry_sink_closed and self._telemetry_client is not None:
                try:
                    self._telemetry_client.close()
                except BaseException as exc:
                    failures.append(exc)
            self._gc_lease.release()
            if failures:
                details = "; ".join(
                    f"{type(exc).__name__}: {exc}"
                    for exc in failures
                )
                raise RuntimeError(
                    f"Subjective runtime cleanup failed: {details}"
                ) from failures[0]
            with self._state_changed:
                self._resources_closed = True

    def heartbeat_takeover_claim(self, claim_id: str) -> None:
        """Keep one gateway-authorized controller lease alive."""
        response = self.client.post(f"/ai/takeover/{claim_id}/heartbeat")
        response.raise_for_status()

    def bootstrap(self) -> None:
        """Fetch snapshot and initialize local state."""
        with self._state_changed:
            self._raise_if_closed()
        self._emit("runtime.bootstrap_started", "Bootstrapping subjective runtime.")
        try:
            response = self.client.get(
                f"/ai/sessions/{self.session_id}/observation/snapshot"
            )
            response.raise_for_status()
        except Exception:
            with self._state_changed:
                self._raise_if_closed()
            raise
        snapshot = ObservationSnapshot.model_validate(response.json())
        with self._state_changed:
            self._raise_if_closed()
            world = self.store.load_snapshot(snapshot)
            if self.evidence_recorder is not None:
                self.evidence_recorder.record_snapshot(snapshot, reason="bootstrap")
            self._run_hooks(HookPoint.SNAPSHOT_LOADED)
            self._stream_error = None
            self._state_changed.notify_all()
        self._emit(
            "runtime.bootstrap_completed",
            "Subjective runtime bootstrap completed.",
            actor_uuid=world.current_epoch.actor_uuid if world.current_epoch else None,
            epoch_id=world.current_epoch.epoch_id if world.current_epoch else None,
            observation_cursor=world.observation_cursor,
            payload={
                "automatic_gc_suspended": automatic_gc_suspended(),
                "retains_observation_history": True,
                "observation_history_start_cursor": self.store.snapshot_observation_cursor,
            },
        )
        self._start_observation_pump()

    def wait_until_stream_synced(self, timeout: float = 10.0) -> None:
        """Wait until the live observation transport proves one valid sync."""
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        if not self._stream_ready.wait(timeout=timeout):
            raise TimeoutError(
                "Subjective observation stream did not synchronize before timeout"
            )
        with self._state_changed:
            self._raise_if_closed()
            stream_error = self._stream_error
            stream_sync_count = self._stream_sync_count
        if stream_error is not None:
            raise RuntimeError(
                "Subjective observation stream failed before synchronization"
            ) from stream_error
        if stream_sync_count < 1:
            raise RuntimeError(
                "Subjective observation stream signaled readiness without a sync"
            )

    def wait_for_epoch(self) -> DecisionEpoch:
        """Wait on the single stream reducer until a controlled epoch exists."""
        with self._state_changed:
            self._raise_if_closed()
        if self.store.world is None:
            self.bootstrap()
        self._start_observation_pump()
        with self._state_changed:
            while True:
                self._raise_if_closed()
                self._raise_if_encounter_ended()
                if self.store.world is not None and self.store.world.current_epoch is not None:
                    return self.store.world.current_epoch
                self._raise_stream_error()
                self._state_changed.wait()

    def _raise_if_closed(self) -> None:
        """Stop cooperative waiters after the runtime lifecycle ends."""
        if self._closed:
            raise SubjectiveRuntimeClosedError(
                f"Subjective runtime for session {self.session_id} is closed."
            )

    def _raise_if_encounter_ended(self) -> None:
        """Stop an epoch wait when the subjective encounter is terminal."""
        world = self.store.world
        if world is not None and world.encounter is not None and world.encounter.state == "ended":
            raise SubjectiveEncounterEndedError(
                f"Encounter {world.encounter.uuid} ended at observation cursor {world.observation_cursor}."
            )

    def apply_frame(self, payload: dict[str, Any]) -> None:
        """Apply one observation frame and run hooks."""
        frame = ObservationFrame.model_validate(payload)
        with self._state_changed:
            result = self.store.apply_frame(frame)
            if result.kind == ApplyResultKind.DUPLICATE:
                return
            if result.kind != ApplyResultKind.GAP:
                if self.evidence_recorder is not None:
                    self.evidence_recorder.record_frame(frame)
                self._run_applied_frame_effects(frame, previous_world=result.previous_world)
                self._state_changed.notify_all()
                return
        if result.kind == ApplyResultKind.GAP:
            self._emit("stream.gap_detected", "Observation cursor gap detected.", level="warning", payload=result.model_dump(mode="json"))
            with self._state_changed:
                self._run_hooks(HookPoint.STREAM_GAP)
            self.resync()
            return

    def _start_observation_pump(self) -> None:
        """Start the runtime's sole subjective-stream consumer exactly once."""
        with self._state_changed:
            if self._closed:
                self._raise_if_closed()
            if self._stream_thread is not None:
                return
            self._stream_thread = Thread(
                target=self._observation_pump,
                name=f"subjective-observation-{self.session_id}",
                daemon=True,
            )
            self._stream_thread.start()

    def _observation_pump(self) -> None:
        """Own one SSE connection and reduce all subjective frames in order."""
        deferred = _DeferredFrameEffects()
        while not self._stream_stop.is_set():
            with self._state_changed:
                cursor = self.store.world.observation_cursor if self.store.world is not None else 0
            try:
                stream_closed = True
                for event_name, payload in self.iter_observation_events(cursor):
                    if self._stream_stop.is_set():
                        return
                    stream_closed = False
                    if event_name == "sync":
                        with self._state_changed:
                            self._stream_event_count += 1
                            self._stream_sync_count += 1
                            self._stream_ready.set()
                            self._state_changed.notify_all()
                        self._emit(
                            "stream.synced",
                            "Observation stream sync received.",
                            payload=payload,
                        )
                        continue
                    if event_name == "heartbeat":
                        with self._state_changed:
                            self._stream_event_count += 1
                        continue
                    if event_name == "observation_frame":
                        deferred = self._apply_pump_frame(payload, deferred)
                        continue
                    if event_name == "evicted":
                        with self._state_changed:
                            self._stream_event_count += 1
                            self._stream_evicted_count += 1
                        self._emit(
                            "stream.evicted",
                            "Observation stream was evicted; resyncing before reconnect.",
                            level="warning",
                            payload=payload,
                        )
                        self.resync()
                        deferred = _DeferredFrameEffects()
                        break
                    if event_name == "error":
                        raise RuntimeError(
                            f"subjective observation stream error: {payload}"
                        )
                if self._stream_stop.is_set():
                    return
                if stream_closed:
                    raise RuntimeError("subjective observation stream closed before sync")
            except SubjectiveObservationGapError:
                if self._stream_stop.is_set():
                    return
                self._emit(
                    "stream.gap_detected",
                    "Observation cursor gap detected; resyncing before reconnect.",
                    level="warning",
                )
                self.resync()
                deferred = _DeferredFrameEffects()
                continue
            except Exception as exc:
                if self._stream_stop.is_set():
                    return
                with self._state_changed:
                    self._stream_error = exc
                    self._stream_ready.set()
                    self._state_changed.notify_all()
                self._emit(
                    "stream.error",
                    "Observation stream consumer stopped after a transport error.",
                    level="error",
                    payload={"error": str(exc)},
                )
                return

    def _apply_pump_frame(
        self,
        payload: dict[str, Any],
        deferred: _DeferredFrameEffects,
    ) -> _DeferredFrameEffects:
        """Apply one pump-owned frame and flush hooks at a command boundary."""
        reduction_started = time.perf_counter()
        parse_started = time.perf_counter()
        frame = ObservationFrame.model_validate(payload)
        parse_ms = _elapsed_ms_float(parse_started)
        with self._state_changed:
            store_started = time.perf_counter()
            result = self.store.apply_frame(
                frame,
                capture_previous=not deferred.applied,
            )
            store_apply_ms = _elapsed_ms_float(store_started)
            self._stream_reduction_ms += _elapsed_ms_float(reduction_started)
            self._stream_frame_parse_ms += parse_ms
            self._stream_store_apply_ms += store_apply_ms
            if result.kind == ApplyResultKind.DUPLICATE:
                return deferred
            if result.kind == ApplyResultKind.GAP:
                error = SubjectiveObservationGapError(
                    "subjective observation cursor gap: "
                    f"expected {result.expected_cursor}, received {result.actual_cursor}"
                )
                self._state_changed.notify_all()
                raise error
            self._stream_event_count += 1
            self._stream_frame_count += 1
            if self.evidence_recorder is not None:
                self.evidence_recorder.record_frame(frame)
            deferred.record(frame, result.previous_world)
            world_ended = (
                self.store.world is not None
                and self.store.world.encounter is not None
                and self.store.world.encounter.state == "ended"
            )
            command_boundary = (
                frame.frame_type == ObservationFrameType.DECISION_EPOCH
                or not self.store.pending_commands
                or world_ended
            )
            if command_boundary:
                hooks_started = time.perf_counter()
                self._flush_deferred_frame_effects(deferred)
                self._stream_hook_ms += _elapsed_ms_float(hooks_started)
                deferred = _DeferredFrameEffects()
            self._state_changed.notify_all()
        return deferred

    def _raise_stream_error(self) -> None:
        """Raise the terminal stream-consumer error while holding the state lock."""
        if self._stream_error is not None:
            raise RuntimeError("subjective observation stream is unavailable") from self._stream_error

    def execute(
        self,
        row_id: str,
        *,
        command_id: Optional[str] = None,
        **options: Any,
    ) -> CommandResult:
        """Execute one row from the current epoch."""
        timing = CommandTimingProbe(command_type="execute", row_id=row_id)
        wait_started = time.perf_counter()
        epoch = self.wait_for_epoch()
        timing.wait_for_epoch_ms += _elapsed_ms_float(wait_started)
        command_id = command_id or str(uuid4())
        timing.command_id = command_id
        timing.actor_uuid = epoch.actor_uuid
        timing.epoch_id = epoch.epoch_id
        payload = {
            "command_id": command_id,
            "actor_uuid": epoch.actor_uuid,
            "basis_epoch_id": epoch.epoch_id,
            "row_id": row_id,
            "extra_target_uuids": options.get("extra_target_uuids"),
            "prefer_safe": options.get("prefer_safe", True),
            "include_diagnostics": self.include_command_diagnostics,
        }
        with self._state_changed:
            self._register_pending_command(
                command_id,
                actor_uuid=epoch.actor_uuid,
                requested_epoch_id=epoch.epoch_id,
                row_id=row_id,
            )
        if self.evidence_recorder is not None:
            self.evidence_recorder.record_command_intent(payload)
        self._emit("command.submitted", f"Submitting command {row_id}.", actor_uuid=epoch.actor_uuid, epoch_id=epoch.epoch_id, payload=payload)
        ack = self._submit_command(
            f"/ai/sessions/{self.session_id}/commands/execute",
            payload,
            command_id,
            timing,
        )
        timing.server_timing = _server_timing_from_ack(ack)
        self._emit(
            f"command.ack.{ack.status.value}",
            ack.message,
            actor_uuid=ack.actor_uuid,
            epoch_id=ack.current_epoch_id or ack.requested_epoch_id,
            payload=ack.model_dump(mode="json"),
        )
        if ack.resync_required:
            with self._state_changed:
                self._discard_pending_command(command_id)
            self._resync_timed(timing)
            self._finish_command_timing(timing, ack)
            return ack
        result = self._wait_for_command_followup(command_id, ack, timing=timing)
        self._finish_command_timing(timing, result)
        return result

    def end_turn(self, *, command_id: Optional[str] = None) -> CommandResult:
        """End the current controlled actor turn."""
        timing = CommandTimingProbe(command_type="end_turn", row_id=END_TURN_ROW_ID)
        wait_started = time.perf_counter()
        epoch = self.wait_for_epoch()
        timing.wait_for_epoch_ms += _elapsed_ms_float(wait_started)
        command_id = command_id or str(uuid4())
        timing.command_id = command_id
        timing.actor_uuid = epoch.actor_uuid
        timing.epoch_id = epoch.epoch_id
        payload = {
            "command_id": command_id,
            "actor_uuid": epoch.actor_uuid,
            "basis_epoch_id": epoch.epoch_id,
            "include_diagnostics": self.include_command_diagnostics,
        }
        with self._state_changed:
            self._register_pending_command(
                command_id,
                actor_uuid=epoch.actor_uuid,
                requested_epoch_id=epoch.epoch_id,
                row_id=END_TURN_ROW_ID,
            )
        if self.evidence_recorder is not None:
            self.evidence_recorder.record_command_intent(payload)
        self._emit("command.submitted", "Submitting end-turn command.", actor_uuid=epoch.actor_uuid, epoch_id=epoch.epoch_id, payload=payload)
        ack = self._submit_command(
            f"/ai/sessions/{self.session_id}/commands/end-turn",
            payload,
            command_id,
            timing,
        )
        timing.server_timing = _server_timing_from_ack(ack)
        self._emit(
            f"command.ack.{ack.status.value}",
            ack.message,
            actor_uuid=ack.actor_uuid,
            epoch_id=ack.current_epoch_id or ack.requested_epoch_id,
            payload=ack.model_dump(mode="json"),
        )
        if ack.resync_required:
            with self._state_changed:
                self._discard_pending_command(command_id)
            self._resync_timed(timing)
            self._finish_command_timing(timing, ack)
            return ack
        result = self._wait_for_command_followup(command_id, ack, timing=timing)
        self._finish_command_timing(timing, result)
        return result

    def _submit_command(
        self,
        path: str,
        payload: dict[str, Any],
        command_id: str,
        timing: CommandTimingProbe,
    ) -> CommandResult:
        """Submit one command and merge its compact acknowledgement safely."""
        submit_started = time.perf_counter()
        try:
            response = self.client.post(path, json=payload)
            timing.submit_http_ms += _elapsed_ms_float(submit_started)
            response.raise_for_status()
            parse_started = time.perf_counter()
            ack = CommandResult.model_validate(response.json())
            timing.ack_parse_ms += _elapsed_ms_float(parse_started)
        except Exception as exc:
            if timing.submit_http_ms == 0:
                timing.submit_http_ms = _elapsed_ms_float(submit_started)
            with self._state_changed:
                self._discard_pending_command(command_id)
                self._state_changed.notify_all()
                self._raise_if_closed()
            if self.evidence_recorder is not None:
                self.evidence_recorder.record_command_transport_failure(
                    command_id,
                    exc,
                )
            raise
        if self.evidence_recorder is not None:
            self.evidence_recorder.record_command_acknowledgement(ack)
        with self._state_changed:
            self.store.register_pending_command(command_id, ack)
            self._state_changed.notify_all()
        return ack

    def _register_pending_command(
        self,
        command_id: str,
        *,
        actor_uuid: str,
        requested_epoch_id: str,
        row_id: str,
    ) -> None:
        """Register command intent and its stream-timing baseline atomically."""
        self._command_stream_baselines.setdefault(
            command_id,
            _CommandStreamBaseline(
                events=self._stream_event_count,
                frames=self._stream_frame_count,
                syncs=self._stream_sync_count,
                evictions=self._stream_evicted_count,
                reduction_ms=self._stream_reduction_ms,
                frame_parse_ms=self._stream_frame_parse_ms,
                store_apply_ms=self._stream_store_apply_ms,
                hook_ms=self._stream_hook_ms,
                resync_generation=self._resync_generation,
                processor_ms=dict(self._stream_processor_ms),
            ),
        )
        self.store.register_pending_command(
            command_id,
            actor_uuid=actor_uuid,
            requested_epoch_id=requested_epoch_id,
            row_id=row_id,
        )

    def _discard_pending_command(self, command_id: str) -> None:
        """Discard command lifecycle and its stream-timing baseline."""
        self.store.discard_pending_command(command_id)
        self._command_stream_baselines.pop(command_id, None)

    def _wait_for_command_followup(
        self,
        command_id: str,
        ack: CommandResult,
        timing: Optional[CommandTimingProbe] = None,
    ) -> CommandResult:
        """Wait for stream-reduced result and terminal control context."""
        sse_started = time.perf_counter()
        with self._state_changed:
            baseline = self._command_stream_baselines.get(
                command_id,
                _CommandStreamBaseline(
                    events=self._stream_event_count,
                    frames=self._stream_frame_count,
                    syncs=self._stream_sync_count,
                    evictions=self._stream_evicted_count,
                    reduction_ms=self._stream_reduction_ms,
                    frame_parse_ms=self._stream_frame_parse_ms,
                    store_apply_ms=self._stream_store_apply_ms,
                    hook_ms=self._stream_hook_ms,
                    resync_generation=self._resync_generation,
                    processor_ms=dict(self._stream_processor_ms),
                ),
            )
            deadline = time.monotonic() + self.command_followup_timeout
            while True:
                self._raise_if_closed()
                if self._resync_generation != baseline.resync_generation:
                    self._command_stream_baselines.pop(command_id, None)
                    return ack.model_copy(update={"resync_required": True})
                streamed_result = self.store.get_command_result(command_id)
                done = (
                    streamed_result is not None
                    and self.store.command_control_seen(command_id)
                )
                if done:
                    assert streamed_result is not None
                    if timing is not None:
                        timing.sse_wait_ms += _elapsed_ms_float(sse_started)
                        timing.sse_events += self._stream_event_count - baseline.events
                        timing.sse_frames += self._stream_frame_count - baseline.frames
                        timing.sse_sync_events += self._stream_sync_count - baseline.syncs
                        timing.sse_evicted_events += self._stream_evicted_count - baseline.evictions
                        timing.stream_reduction_ms += (
                            self._stream_reduction_ms - baseline.reduction_ms
                        )
                        timing.stream_frame_parse_ms += (
                            self._stream_frame_parse_ms - baseline.frame_parse_ms
                        )
                        timing.stream_store_apply_ms += (
                            self._stream_store_apply_ms - baseline.store_apply_ms
                        )
                        timing.stream_hook_ms += (
                            self._stream_hook_ms - baseline.hook_ms
                        )
                        timing.stream_processor_ms = {
                            name: elapsed_ms - baseline.processor_ms.get(name, 0.0)
                            for name, elapsed_ms in self._stream_processor_ms.items()
                            if elapsed_ms - baseline.processor_ms.get(name, 0.0) > 0.0
                        }
                    self._command_stream_baselines.pop(command_id, None)
                    return streamed_result
                self._raise_stream_error()
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    self._discard_pending_command(command_id)
                    break
                self._state_changed.wait(timeout=remaining)
        with self._state_changed:
            self._raise_if_closed()
        if timing is not None:
            timing.sse_wait_ms += _elapsed_ms_float(sse_started)
        self._resync_timed(timing)
        return (self.store.get_command_result(command_id) or ack).model_copy(
            update={"resync_required": True}
        )

    def _run_applied_frame_effects(self, frame: ObservationFrame, previous_world: Any = None) -> None:
        """Run hooks and telemetry for one already-applied frame."""
        self._run_hooks(HookPoint.FRAME_APPLIED, previous_world=previous_world)
        self._emit_frame_control_effects(frame, previous_world=previous_world)

    def _flush_deferred_frame_effects(self, deferred: _DeferredFrameEffects) -> None:
        """Run stream hooks once after a command-caused event batch materializes."""
        if not deferred.applied:
            return
        self._run_hooks(HookPoint.FRAME_APPLIED, previous_world=deferred.previous_world)
        for frame in deferred.command_result_frames:
            self._run_command_result_effects(frame, previous_world=deferred.previous_world)
        if deferred.epoch_started_frames:
            self._run_hooks(HookPoint.EPOCH_STARTED, previous_world=deferred.previous_world)
        for frame in deferred.epoch_started_frames:
            self._emit_epoch_started(frame)
        for frame in deferred.epoch_cleared_frames:
            self._emit_epoch_cleared(frame)

    def _emit_frame_control_effects(self, frame: ObservationFrame, previous_world: Any = None) -> None:
        """Emit hooks and telemetry tied to command/epoch control frames."""
        if frame.command_result is not None:
            self._run_command_result_effects(frame, previous_world=previous_world)
        if frame.frame_type == ObservationFrameType.DECISION_EPOCH and frame.decision_epoch is not None:
            self._run_hooks(HookPoint.EPOCH_STARTED, previous_world=previous_world)
            self._emit_epoch_started(frame)
        elif frame.frame_type == ObservationFrameType.DECISION_EPOCH:
            self._emit_epoch_cleared(frame)

    def _run_command_result_effects(self, frame: ObservationFrame, previous_world: Any = None) -> None:
        """Run command-result hook and telemetry for one control frame."""
        if frame.command_result is None:
            return
        if (
            frame.command_result.status is CommandResultStatus.ACCEPTED
            and frame.command_result.action_resolution is ActionResolutionStatus.CANCELED
        ):
            hook = HookPoint.ACTION_CANCELED
        elif (
            frame.command_result.status is CommandResultStatus.ACCEPTED
            and frame.command_result.action_resolution is ActionResolutionStatus.INTERRUPTED
        ):
            hook = HookPoint.ACTION_INTERRUPTED
        else:
            hook = {
                CommandResultStatus.ACCEPTED: HookPoint.ACTION_COMPLETED,
                CommandResultStatus.REJECTED: HookPoint.ACTION_REJECTED,
                CommandResultStatus.STALE: HookPoint.ACTION_STALE,
            }.get(frame.command_result.status)
        if hook is not None:
            self._run_hooks(hook, previous_world=previous_world)
        self._emit(
            f"command.stream_result.{frame.command_result.status.value}",
            frame.command_result.message,
            actor_uuid=frame.command_result.actor_uuid,
            epoch_id=frame.command_result.current_epoch_id or frame.command_result.requested_epoch_id,
            observation_cursor=frame.observation_cursor,
            payload=frame.command_result.model_dump(mode="json"),
        )

    def _emit_epoch_started(self, frame: ObservationFrame) -> None:
        """Emit telemetry for one decision-epoch start frame."""
        if frame.decision_epoch is None:
            return
        self._emit(
            "epoch.started",
            "Decision epoch started.",
            actor_uuid=frame.decision_epoch.actor_uuid,
            epoch_id=frame.decision_epoch.epoch_id,
            observation_cursor=frame.observation_cursor,
        )

    def _emit_epoch_cleared(self, frame: ObservationFrame) -> None:
        """Emit telemetry for one decision-epoch clear frame."""
        self._emit(
            "epoch.cleared",
            "Decision epoch cleared.",
            observation_cursor=frame.observation_cursor,
            payload={"source_command_id": frame.source_command_id},
        )

    def resync(self) -> None:
        """Reload a fresh snapshot."""
        with self._state_changed:
            self._raise_if_closed()
        self._emit("stream.resync_started", "Resyncing subjective runtime.")
        try:
            response = self.client.get(
                f"/ai/sessions/{self.session_id}/observation/snapshot"
            )
            response.raise_for_status()
        except Exception:
            with self._state_changed:
                self._raise_if_closed()
            raise
        snapshot = ObservationSnapshot.model_validate(response.json())
        with self._state_changed:
            self._raise_if_closed()
            self.store.load_snapshot(snapshot)
            if self.evidence_recorder is not None:
                self.evidence_recorder.record_snapshot(snapshot, reason="resync")
            self._run_hooks(HookPoint.RESYNC_COMPLETED)
            self._stream_error = None
            self._resync_generation += 1
            self._state_changed.notify_all()
        self._emit("stream.resync_completed", "Subjective runtime resynced.")

    def _resync_timed(self, timing: Optional[CommandTimingProbe]) -> None:
        """Run resync while attributing elapsed time to an optional command probe."""
        if timing is None:
            self.resync()
            return
        started = time.perf_counter()
        self.resync()
        timing.resync_ms += _elapsed_ms_float(started)

    def _finish_command_timing(self, timing: CommandTimingProbe, result: CommandResult) -> None:
        """Emit final timing telemetry for one command lifecycle."""
        timing.status = result.status.value
        timing.resync_required = result.resync_required
        payload = timing.model_dump()
        self.last_command_timing = payload
        self._emit(
            "runtime.command_timing",
            "Subjective command timing breakdown.",
            level="debug",
            actor_uuid=result.actor_uuid or timing.actor_uuid,
            epoch_id=result.current_epoch_id or result.requested_epoch_id or timing.epoch_id,
            observation_cursor=result.accepted_at_observation_cursor,
            payload=payload,
        )

    def emit_event(
        self,
        event_type: str,
        summary: str,
        *,
        level: str = "info",
        actor_uuid: Optional[str] = None,
        epoch_id: Optional[str] = None,
        observation_cursor: Optional[int] = None,
        payload: Optional[dict[str, Any]] = None,
        event_id: Optional[str] = None,
        source: str = "ai.subjective.runtime",
        tags: Optional[list[str]] = None,
    ) -> None:
        """Emit one structured agent event."""
        self._emit(
            event_type,
            summary,
            level=level,
            actor_uuid=actor_uuid,
            epoch_id=epoch_id,
            observation_cursor=observation_cursor,
            payload=payload,
            event_id=event_id,
            source=source,
            tags=tags,
        )

    def emit_policy_decision(self, event: PolicyDecisionTelemetry) -> None:
        """Publish one canonical shared-policy decision as agent telemetry."""
        correlation = event.correlation
        self._emit(
            "policy.decision_evaluated",
            "Shared policy decision evaluated.",
            actor_uuid=correlation.actor_uuid,
            epoch_id=correlation.epoch_id,
            observation_cursor=correlation.observation_cursor,
            payload=event.model_dump(mode="json"),
            event_id=event.event_id,
            source="ai.policy.host",
            tags=["policy", "decision", event.controller_mode],
        )

    def iter_observation_events(self, since: int) -> Iterator[tuple[str, dict[str, Any]]]:
        """Yield parsed SSE events from the observation stream."""
        with self.stream_client.stream(
            "GET",
            f"/ai/sessions/{self.session_id}/observation/subscribe",
            params={"since": since},
        ) as response:
            with self._state_changed:
                if self._closed:
                    interrupt_immediately = True
                else:
                    interrupt_immediately = False
                    self._active_stream_response = response
            if interrupt_immediately:
                _interrupt_httpx_response_read(response)
                return
            try:
                response.raise_for_status()
                event_name = "message"
                data_lines: list[str] = []
                for line in response.iter_lines():
                    if line == "":
                        if data_lines:
                            yield event_name, json.loads("\n".join(data_lines))
                        event_name = "message"
                        data_lines = []
                        continue
                    if line.startswith("event:"):
                        event_name = line[6:].strip()
                    elif line.startswith("data:"):
                        data_lines.append(line[5:].strip())
            finally:
                with self._state_changed:
                    if self._active_stream_response is response:
                        self._active_stream_response = None

    def _run_hooks(self, hook: HookPoint, previous_world: Any = None) -> None:
        """Run hook processors and update AgentState."""
        if self.store.world is None:
            return
        context = HookContext(
            hook=hook,
            world=self.store.world,
            agent_state=self.store.agent_state,
            previous_world=previous_world,
        )
        self.store.agent_state = self.hooks.run(context)
        for name, elapsed_ms in self.hooks.last_timings_ms.items():
            self._stream_processor_ms[name] = (
                self._stream_processor_ms.get(name, 0.0) + elapsed_ms
            )

    def _emit(
        self,
        event_type: str,
        summary: str,
        *,
        level: str = "info",
        actor_uuid: Optional[str] = None,
        epoch_id: Optional[str] = None,
        observation_cursor: Optional[int] = None,
        payload: Optional[dict[str, Any]] = None,
        event_id: Optional[str] = None,
        source: str = "ai.subjective.runtime",
        tags: Optional[list[str]] = None,
    ) -> None:
        """Emit one agent event."""
        if self.store.world is not None:
            observation_cursor = observation_cursor if observation_cursor is not None else self.store.world.observation_cursor
        event = AgentEvent(
            event_id=event_id or str(uuid4()),
            session_id=self.session_id,
            actor_uuid=actor_uuid,
            epoch_id=epoch_id,
            observation_cursor=observation_cursor,
            event_type=event_type,
            level=level,  # type: ignore[arg-type]
            source=source,
            summary=summary,
            payload=payload or {},
            tags=tags or [],
        )
        if self.evidence_recorder is not None:
            self.evidence_recorder.record_agent_event(event)
        self.event_sink.emit(event)


def _server_timing_from_ack(ack: CommandResult) -> Optional[dict[str, Any]]:
    """Extract server-side command timing from a compact HTTP ack."""
    if not isinstance(ack.payload, dict):
        return None
    timing = ack.payload.get("server_timing")
    return timing if isinstance(timing, dict) else None


def _interrupt_httpx_response_read(response: httpx.Response) -> None:
    """Close the transport stream that owns an active blocking response read."""
    network_stream = response.extensions.get("network_stream")
    get_extra_info = getattr(network_stream, "get_extra_info", None)
    if callable(get_extra_info):
        transport_socket = get_extra_info("socket")
        shutdown_socket = getattr(transport_socket, "shutdown", None)
        if callable(shutdown_socket):
            try:
                shutdown_socket(socket.SHUT_RDWR)
            except OSError:
                # The peer or observation worker may have won the close race.
                pass
    close_network_stream = getattr(network_stream, "close", None)
    if callable(close_network_stream):
        close_network_stream()
        return
    response.close()


def _elapsed_ms_float(started: float) -> float:
    """Return unrounded elapsed milliseconds from a perf-counter start."""
    return (time.perf_counter() - started) * 1000


def _elapsed_ms(started: float) -> float:
    """Return rounded elapsed milliseconds from a perf-counter start."""
    return _round_ms(_elapsed_ms_float(started))


def _round_ms(value: float) -> float:
    """Round a millisecond value for compact telemetry."""
    return round(value, 3)
