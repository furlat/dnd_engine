"""HTTP/SSE runtime client for subjective AI controllers."""

from __future__ import annotations

import gc
import json
import logging
from queue import Queue
from threading import Condition, Event as ThreadEvent, RLock, Thread
import time
from dataclasses import dataclass, field
from typing import Any, Iterator, Optional, Protocol
from uuid import uuid4

import httpx

from ai.observation.models import ObservationFrame, ObservationFrameType
from ai.policy.contracts import PolicyDecisionTelemetry
from ai.protocol.control import (
    ActionResolutionStatus,
    CommandResult,
    CommandResultStatus,
    DecisionEpoch,
)
from ai.subjective.hooks import HookContext, HookPoint, HookRegistry
from ai.subjective.models import AgentEvent
from ai.subjective.processors import default_processors
from ai.subjective.queries import SubjectiveQueries
from ai.subjective.runtime_gc import AutomaticGcLease, automatic_gc_suspended
from ai.subjective.store import ApplyResultKind, SubjectiveStore

logger = logging.getLogger(__name__)
_AGENT_EVENT_CLOSE = object()


class SubjectiveEncounterEndedError(RuntimeError):
    """Raised when an epoch wait reaches a terminal subjective encounter."""


class SubjectiveObservationGapError(RuntimeError):
    """Raised internally when the live stream skips an observation cursor."""


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

    def __init__(self, destination: AgentEventSink, *, max_depth: int = 1024) -> None:
        """Create one bounded telemetry delivery worker.

        Args:
            destination: Synchronous sink owned by the worker thread.
            max_depth: Maximum number of pending event batches.
        """
        if max_depth < 1:
            raise ValueError("max_depth must be positive")
        self.destination = destination
        self._queue: Queue[list[AgentEvent] | object] = Queue(max_depth)
        self._closed = False
        self._worker = Thread(
            target=self._deliver,
            name="agent-event-delivery",
            daemon=True,
        )
        self._worker.start()

    def emit(self, event: AgentEvent) -> None:
        """Enqueue one immutable event in source order."""
        self.emit_many([event])

    def emit_many(self, events: list[AgentEvent]) -> None:
        """Enqueue one ordered event batch."""
        if self._closed:
            raise RuntimeError("agent event sink is closed")
        if events:
            self._queue.put(list(events))

    def flush(self) -> None:
        """Wait until every previously queued event is delivered."""
        self._queue.join()

    def close(self) -> None:
        """Flush and stop the delivery worker exactly once."""
        if self._closed:
            return
        self._closed = True
        self._queue.put(_AGENT_EVENT_CLOSE)
        self._worker.join()

    def _deliver(self) -> None:
        """Run synchronous telemetry transport outside gameplay threads."""
        while True:
            queued = self._queue.get()
            try:
                if queued is _AGENT_EVENT_CLOSE:
                    return
                assert isinstance(queued, list)
                try:
                    self.destination.emit_many(queued)
                except Exception:
                    logger.exception("agent event delivery failed")
            finally:
                self._queue.task_done()


class SubjectiveRuntime:
    """Long-lived local runtime for one AI session."""

    def __init__(
        self,
        base_url: str,
        session_id: str,
        *,
        event_sink: Optional[AgentEventSink] = None,
        processors: Optional[list] = None,
        command_followup_timeout: float = 10.0,
    ) -> None:
        """Create a runtime client."""
        self.base_url = base_url.rstrip("/")
        self.session_id = session_id
        self.client = httpx.Client(base_url=self.base_url, timeout=httpx.Timeout(connect=5.0, read=None, write=10.0, pool=5.0))
        self.stream_client = httpx.Client(base_url=self.base_url, timeout=httpx.Timeout(connect=5.0, read=None, write=10.0, pool=5.0))
        self.store = SubjectiveStore()
        self.state_lock = RLock()
        self._state_changed = Condition(self.state_lock)
        self._stream_stop = ThreadEvent()
        self._stream_ready = ThreadEvent()
        self._stream_thread: Optional[Thread] = None
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
        self.command_followup_timeout = command_followup_timeout
        self.hooks = HookRegistry(processors if processors is not None else default_processors())
        self.event_sink = event_sink or QueuedAgentEventSink(
            CompositeAgentEventSink([
                LoggingAgentEventSink(),
                HttpAgentEventSink(self.client, session_id),
            ])
        )
        self.last_command_timing: Optional[dict[str, Any]] = None
        self._gc_lease = AutomaticGcLease.acquire()

    @property
    def query(self) -> SubjectiveQueries:
        """Return local query facade."""
        with self.state_lock:
            if self.store.world is None:
                raise RuntimeError("SubjectiveRuntime.bootstrap() must be called before query access.")
            return SubjectiveQueries(self.store.world, self.store.agent_state)

    def close(self) -> None:
        """Close network resources."""
        if self._closed:
            return
        self._closed = True
        try:
            self._stream_stop.set()
            self.stream_client.close()
            stream_thread = self._stream_thread
            if stream_thread is not None and stream_thread.is_alive():
                stream_thread.join(timeout=2.0)
            close_sink = getattr(self.event_sink, "close", None)
            if callable(close_sink):
                close_sink()
            self.client.close()
        finally:
            self._gc_lease.release()

    def flush_agent_events(self) -> None:
        """Wait until queued runtime telemetry reaches its destination."""
        flush_sink = getattr(self.event_sink, "flush", None)
        if callable(flush_sink):
            flush_sink()

    def bootstrap(self) -> None:
        """Fetch snapshot and initialize local state."""
        self._emit("runtime.bootstrap_started", "Bootstrapping subjective runtime.")
        response = self.client.get(f"/ai/sessions/{self.session_id}/observation/snapshot")
        response.raise_for_status()
        with self._state_changed:
            world = self.store.load_snapshot(response.json())
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
                "retains_observation_history": False,
            },
        )
        self._start_observation_pump()

    def wait_for_epoch(self) -> DecisionEpoch:
        """Wait on the single stream reducer until a controlled epoch exists."""
        if self.store.world is None:
            self.bootstrap()
        self._start_observation_pump()
        with self._state_changed:
            while True:
                self._raise_if_encounter_ended()
                if self.store.world is not None and self.store.world.current_epoch is not None:
                    return self.store.world.current_epoch
                self._raise_stream_error()
                self._state_changed.wait()
            self._raise_if_encounter_ended()
            if self.store.world and self.store.world.current_epoch is not None:
                return self.store.world.current_epoch

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
                raise RuntimeError("Subjective runtime is closed")
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
            "include_diagnostics": True,
        }
        with self._state_changed:
            self._register_pending_command(
                command_id,
                actor_uuid=epoch.actor_uuid,
                requested_epoch_id=epoch.epoch_id,
                row_id=row_id,
            )
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
        timing = CommandTimingProbe(command_type="end_turn", row_id="special|End Turn|index=0")
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
            "include_diagnostics": True,
        }
        with self._state_changed:
            self._register_pending_command(
                command_id,
                actor_uuid=epoch.actor_uuid,
                requested_epoch_id=epoch.epoch_id,
                row_id="special|End Turn|index=0",
            )
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
        except Exception:
            if timing.submit_http_ms == 0:
                timing.submit_http_ms = _elapsed_ms_float(submit_started)
            with self._state_changed:
                self._discard_pending_command(command_id)
                self._state_changed.notify_all()
            raise
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
        self._emit("stream.resync_started", "Resyncing subjective runtime.")
        response = self.client.get(f"/ai/sessions/{self.session_id}/observation/snapshot")
        response.raise_for_status()
        with self._state_changed:
            self.store.load_snapshot(response.json())
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
        self.event_sink.emit(event)


def _server_timing_from_ack(ack: CommandResult) -> Optional[dict[str, Any]]:
    """Extract server-side command timing from a compact HTTP ack."""
    if not isinstance(ack.payload, dict):
        return None
    timing = ack.payload.get("server_timing")
    return timing if isinstance(timing, dict) else None


def _elapsed_ms_float(started: float) -> float:
    """Return unrounded elapsed milliseconds from a perf-counter start."""
    return (time.perf_counter() - started) * 1000


def _elapsed_ms(started: float) -> float:
    """Return rounded elapsed milliseconds from a perf-counter start."""
    return _round_ms(_elapsed_ms_float(started))


def _round_ms(value: float) -> float:
    """Round a millisecond value for compact telemetry."""
    return round(value, 3)
