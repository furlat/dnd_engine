"""Seamless event-first observation/runtime contract tests."""

import asyncio
from collections.abc import AsyncGenerator
import gc
import json
from queue import Empty, Queue
import socket
from threading import Event as ThreadEvent, Thread
import time
from typing import Any, Sequence, cast
from uuid import UUID
from uuid import uuid4

import httpx
import pytest
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
import uvicorn

import server.agent_runtime.observation_projector as observation_projector
from ai.ordered_delivery import OrderedDeliveryTimeoutError
from server.agent_protocol.observation import ObservationFrame, ObservationFrameType, ObservationSourceKind
from server.agent_runtime.observation_projector import (
    append_observation_control_frame,
    observation_wakeup_stream,
)
from server.agent_protocol.control import (
    ActionResolutionStatus,
    CommandResult,
    CommandResultStatus,
    DecisionEpoch,
    END_TURN_ROW_ID,
)
from ai.subjective.hooks import HookContext, HookPoint, ProcessorOutput
from ai.subjective.runtime import (
    CommandTimingProbe,
    MemoryAgentEventSink,
    QueuedAgentEventSink,
    SubjectiveRuntime,
    SubjectiveRuntimeClosedError,
)
from ai.subjective.runtime_gc import (
    AutomaticGcLease,
    PRESERVE_AUTOMATIC_GC,
    automatic_gc_suspended,
)
from dnd.action_timing import reset_action_timing_recorder, set_action_timing_recorder
from dnd.actions_functional import execute_by_index
from dnd.core.events import (
    Event,
    EventPhase,
    EventQueue,
    EventType,
    SensoryUpdateEvent,
    SensoryUpdateReason,
)
from dnd.scenarios.ai_validation_arenas import create_ai_validation_arena
from server.session import PlayerType
from server import event_server
from server.api_models import ActionResult
from server.agent_protocol.telemetry import AgentEvent
from server.event_stream import BoundedSubscription
from tests.manual.test_28_subjective_observation_stream import create_observation_game


def _first_affordable_position_row(epoch: dict) -> dict:
    """Return a legal movement row from a decision epoch."""
    typed_epoch = DecisionEpoch.model_validate(epoch)
    for row in typed_epoch.affordances.position_actions:
        if row.can_afford:
            return row.model_dump(mode="json")
    raise AssertionError("Expected at least one affordable position affordance")


def test_server_command_timing_retains_phase_multiplicity_and_maximum() -> None:
    """Aggregated timings must expose repeated work instead of hiding it in totals."""
    timing = event_server._ServerCommandTiming("probe")

    timing.add_elapsed("repeated_phase_ms", 1.25)
    timing.add_elapsed("repeated_phase_ms", 3.5)
    timing.add_elapsed("single_phase_ms", 2.0)

    payload = timing.payload()

    assert payload["phases"]["repeated_phase_ms"] == 4.75
    assert payload["phase_counts"]["repeated_phase_ms"] == 2
    assert payload["phase_max_ms"]["repeated_phase_ms"] == 3.5
    assert payload["phase_counts"]["single_phase_ms"] == 1
    assert payload["phase_max_ms"]["single_phase_ms"] == 2.0


class _CountingProcessor:
    """Processor probe recording hook invocations."""

    name = "counting_probe"
    order = 1

    def __init__(self) -> None:
        self.hooks: list[HookPoint] = []

    def run(self, context: HookContext) -> list[ProcessorOutput]:
        self.hooks.append(context.hook)
        return []


def _start_queue_backed_observation_pump(
    monkeypatch,
    runtime: SubjectiveRuntime,
    *,
    sync_cursor: int,
) -> tuple[Queue[tuple[str, dict]], list[int]]:
    """Start the real runtime pump against a controllable long-lived SSE feed."""
    events: Queue[tuple[str, dict]] = Queue()
    connection_cursors: list[int] = []

    def iter_events(since: int):
        connection_cursors.append(since)
        yield "sync", {"observation_cursor": sync_cursor}
        while not runtime._stream_stop.is_set():
            try:
                yield events.get(timeout=0.01)
            except Empty:
                continue

    monkeypatch.setattr(runtime, "iter_observation_events", iter_events)
    runtime._start_observation_pump()
    assert runtime._stream_ready.wait(timeout=1.0)
    return events, connection_cursors


def test_runtime_service_readiness_requires_successful_stream_sync(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Managed readiness succeeds only after the pump consumes a sync."""
    runtime = SubjectiveRuntime(
        "http://testserver",
        "readiness-session",
        event_sink=MemoryAgentEventSink(),
        processors=[],
    )
    try:
        _start_queue_backed_observation_pump(
            monkeypatch,
            runtime,
            sync_cursor=0,
        )
        runtime.wait_until_stream_synced(timeout=0.5)
    finally:
        runtime.close()


def test_runtime_service_readiness_surfaces_stream_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The pump's error wake-up cannot be mistaken for a valid sync."""
    runtime = SubjectiveRuntime(
        "http://testserver",
        "readiness-error-session",
        event_sink=MemoryAgentEventSink(),
        processors=[],
    )

    def fail_stream(_since: int):
        raise RuntimeError("stream refused")
        yield

    monkeypatch.setattr(runtime, "iter_observation_events", fail_stream)
    runtime._start_observation_pump()
    try:
        with pytest.raises(
            RuntimeError,
            match="failed before synchronization",
        ):
            runtime.wait_until_stream_synced(timeout=0.5)
    finally:
        runtime.close()


def test_runtime_close_cooperatively_interrupts_epoch_wait(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Embedded owners can stop a policy waiter without a transport failure."""
    client, session_id, _hero, _monster, _encounter = create_observation_game()
    snapshot = client.get(
        f"/ai/sessions/{session_id}/observation/snapshot"
    ).json()
    runtime = SubjectiveRuntime(
        "http://testserver",
        session_id,
        event_sink=MemoryAgentEventSink(),
        processors=[],
        gc_policy=PRESERVE_AUTOMATIC_GC,
    )
    runtime.store.load_snapshot(snapshot)
    assert runtime.store.world is not None
    runtime.store.world = runtime.store.world.model_copy(
        update={"current_epoch": None}
    )
    monkeypatch.setattr(runtime, "_start_observation_pump", lambda: None)
    failures: Queue[BaseException] = Queue()

    def wait_for_epoch() -> None:
        try:
            runtime.wait_for_epoch()
        except BaseException as exc:
            failures.put(exc)

    waiter = Thread(target=wait_for_epoch)
    waiter.start()
    try:
        deadline = time.monotonic() + 1.0
        while not waiter.is_alive() and time.monotonic() < deadline:
            time.sleep(0.001)
        runtime.close()
        waiter.join(timeout=1.0)
    finally:
        runtime.close()

    assert not waiter.is_alive()
    assert isinstance(failures.get_nowait(), SubjectiveRuntimeClosedError)


def test_runtime_close_interrupts_command_followup_without_resync(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Shutdown cannot wait for the command timeout or start recovery work."""
    client, session_id, _hero, _monster, _encounter = create_observation_game()
    snapshot = client.get(
        f"/ai/sessions/{session_id}/observation/snapshot"
    ).json()
    epoch = snapshot["current_epoch"]
    command_id = str(uuid4())
    ack = CommandResult(
        status=CommandResultStatus.ACCEPTED,
        command_id=command_id,
        session_id=session_id,
        actor_uuid=epoch["actor_uuid"],
        requested_epoch_id=epoch["epoch_id"],
        row_id="position|Move|pos=1,1",
        message="http ack",
        resync_required=False,
    )
    runtime = SubjectiveRuntime(
        "http://testserver",
        session_id,
        event_sink=MemoryAgentEventSink(),
        processors=[],
        command_followup_timeout=10.0,
        gc_policy=PRESERVE_AUTOMATIC_GC,
    )
    runtime.store.load_snapshot(snapshot)
    with runtime._state_changed:
        runtime.store.register_pending_command(command_id, ack)
    resync_calls: list[bool] = []
    monkeypatch.setattr(
        runtime,
        "resync",
        lambda: resync_calls.append(True),
    )
    failures: Queue[BaseException] = Queue()

    def wait_for_followup() -> None:
        try:
            runtime._wait_for_command_followup(command_id, ack)
        except BaseException as exc:
            failures.put(exc)

    waiter = Thread(target=wait_for_followup)
    waiter.start()
    try:
        deadline = time.monotonic() + 1.0
        while not waiter.is_alive() and time.monotonic() < deadline:
            time.sleep(0.001)
        runtime.request_close()
        waiter.join(timeout=1.0)
    finally:
        runtime.close()

    assert not waiter.is_alive()
    assert isinstance(failures.get_nowait(), SubjectiveRuntimeClosedError)
    assert resync_calls == []


def test_runtime_close_aborts_blocked_control_request() -> None:
    """Embedded shutdown interrupts a blocked snapshot transport promptly."""

    class _BlockingClient:
        def __init__(self) -> None:
            self.entered = ThreadEvent()
            self.closed = ThreadEvent()

        def get(self, _path: str) -> None:
            self.entered.set()
            self.closed.wait()
            raise httpx.ReadError("transport closed")

        def close(self) -> None:
            self.closed.set()

    runtime = SubjectiveRuntime(
        "http://testserver",
        "blocked-control-session",
        event_sink=MemoryAgentEventSink(),
        processors=[],
        gc_policy=PRESERVE_AUTOMATIC_GC,
    )
    blocking_client = _BlockingClient()
    runtime.client.close()
    runtime.client = cast(Any, blocking_client)
    failures: Queue[BaseException] = Queue()

    def bootstrap() -> None:
        try:
            runtime.bootstrap()
        except BaseException as exc:
            failures.put(exc)

    worker = Thread(target=bootstrap)
    worker.start()
    assert blocking_client.entered.wait(timeout=1.0)
    started = time.monotonic()
    try:
        runtime.request_close()
        worker.join(timeout=1.0)
    finally:
        runtime.close()

    assert time.monotonic() - started < 1.0
    assert not worker.is_alive()
    assert isinstance(failures.get_nowait(), SubjectiveRuntimeClosedError)


def test_runtime_shutdown_drains_telemetry_before_closing_its_transport(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cooperative stop must not close the destination of accepted telemetry."""

    class _Response:
        def raise_for_status(self) -> None:
            return None

    class _LifecycleClient:
        def __init__(self, *args: object, **kwargs: object) -> None:
            del args, kwargs
            self.closed = False
            self.post_started = ThreadEvent()
            self.release_post = ThreadEvent()
            self.posts: list[str] = []

        def post(self, path: str, **kwargs: object) -> _Response:
            del kwargs
            self.post_started.set()
            self.release_post.wait(timeout=1.0)
            if self.closed:
                raise RuntimeError("client has been closed")
            self.posts.append(path)
            return _Response()

        def close(self) -> None:
            self.closed = True
            self.release_post.set()

    monkeypatch.setattr(
        "ai.subjective.runtime.httpx.Client",
        _LifecycleClient,
    )
    runtime = SubjectiveRuntime(
        "http://testserver",
        "telemetry-shutdown-session",
        processors=[],
        gc_policy=PRESERVE_AUTOMATIC_GC,
    )
    queued_sink = cast(QueuedAgentEventSink, runtime.event_sink)
    composite = cast(Any, queued_sink.destination)
    telemetry_client = composite.sinks[1].client

    runtime.emit_event("runtime.test", "accepted before shutdown")
    assert telemetry_client.post_started.wait(timeout=1.0)
    try:
        runtime.request_close()

        assert runtime.client.closed is True
        assert runtime.stream_client.closed is True
        assert telemetry_client.closed is False
    finally:
        telemetry_client.release_post.set()
        runtime.close()

    assert telemetry_client.posts == [
        "/ai/sessions/telemetry-shutdown-session/agent-events"
    ]
    assert telemetry_client.closed is True
    assert queued_sink.worker_alive is False


def test_runtime_close_interrupts_active_httpx_stream_before_joining_worker() -> None:
    """The owner closes an active SSE network stream, not only its idle client pool."""

    class _BlockingSocket:
        def __init__(self) -> None:
            self.shutdown_called = ThreadEvent()

        def shutdown(self, how: int) -> None:
            assert how == socket.SHUT_RDWR
            self.shutdown_called.set()

    class _BlockingNetworkStream:
        def __init__(self) -> None:
            self.socket = _BlockingSocket()
            self.closed = ThreadEvent()

        def get_extra_info(self, key: str) -> object | None:
            return self.socket if key == "socket" else None

        def close(self) -> None:
            self.closed.set()

    class _BlockingResponse:
        def __init__(self) -> None:
            self.network_stream = _BlockingNetworkStream()
            self.extensions = {"network_stream": self.network_stream}
            self.read_started = ThreadEvent()
            self.response_closed = False

        def raise_for_status(self) -> None:
            return None

        def iter_lines(self):
            yield "event: sync"
            yield "data: {\"observation_cursor\": 0}"
            yield ""
            self.read_started.set()
            assert self.network_stream.socket.shutdown_called.wait(timeout=1.0)
            raise httpx.ReadError("active network stream interrupted")

        def close(self) -> None:
            # This mirrors HTTPX's active response behavior: Response.close()
            # does not interrupt a concurrent blocking socket read.
            self.response_closed = True

    class _BlockingStreamContext:
        def __init__(self, response: _BlockingResponse) -> None:
            self.response = response

        def __enter__(self) -> _BlockingResponse:
            return self.response

        def __exit__(self, *_args: object) -> None:
            self.response.close()

    class _ActiveStreamClient:
        def __init__(self) -> None:
            self.response = _BlockingResponse()
            self.client_closed = False

        def stream(self, *_args: object, **_kwargs: object) -> _BlockingStreamContext:
            return _BlockingStreamContext(self.response)

        def close(self) -> None:
            # Closing an HTTPX client closes idle pool connections, not the
            # response stream currently checked out by another thread.
            self.client_closed = True

    class _CloseTrackingSink(MemoryAgentEventSink):
        def __init__(self) -> None:
            super().__init__()
            self.closed = False

        def close(self) -> None:
            self.closed = True

    sink = _CloseTrackingSink()
    runtime = SubjectiveRuntime(
        "http://testserver",
        "active-stream-close-session",
        event_sink=sink,
        processors=[],
        gc_policy=PRESERVE_AUTOMATIC_GC,
    )
    stream_client = _ActiveStreamClient()
    runtime.stream_client.close()
    runtime.stream_client = cast(Any, stream_client)
    runtime._start_observation_pump()
    assert stream_client.response.read_started.wait(timeout=1.0)

    runtime.close(timeout_seconds=0.5)

    assert stream_client.client_closed is True
    assert stream_client.response.network_stream.socket.shutdown_called.is_set()
    assert stream_client.response.network_stream.closed.is_set()
    assert stream_client.response.response_closed is True
    assert runtime._stream_thread is not None
    assert runtime._stream_thread.is_alive() is False
    assert sink.closed is True


def test_runtime_close_interrupts_real_uvicorn_sse_socket() -> None:
    """A real unbounded HTTPX read exits inside the runtime close deadline."""
    app = FastAPI()

    @app.get("/ai/sessions/{session_id}/observation/subscribe")
    async def subscribe(session_id: str, since: int = 0) -> StreamingResponse:
        del session_id, since

        async def events() -> AsyncGenerator[str, None]:
            yield "event: sync\ndata: {\"observation_cursor\": 0}\n\n"
            while True:
                await asyncio.sleep(10.0)
                yield "event: heartbeat\ndata: {}\n\n"

        return StreamingResponse(events(), media_type="text/event-stream")

    listen_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listen_socket.bind(("127.0.0.1", 0))
    port = int(listen_socket.getsockname()[1])
    server = uvicorn.Server(uvicorn.Config(
        app,
        log_level="critical",
        timeout_graceful_shutdown=1,
    ))
    server_thread = Thread(
        target=server.run,
        kwargs={"sockets": [listen_socket]},
        daemon=True,
    )
    server_thread.start()
    runtime: SubjectiveRuntime | None = None
    try:
        startup_deadline = time.monotonic() + 2.0
        while not server.started and time.monotonic() < startup_deadline:
            time.sleep(0.01)
        assert server.started

        runtime = SubjectiveRuntime(
            f"http://127.0.0.1:{port}",
            "real-uvicorn-stream-session",
            event_sink=MemoryAgentEventSink(),
            processors=[],
            gc_policy=PRESERVE_AUTOMATIC_GC,
        )
        runtime._start_observation_pump()
        assert runtime._stream_ready.wait(timeout=2.0)
        assert runtime._active_stream_response is not None
        assert (
            runtime._active_stream_response.extensions.get("network_stream")
            is not None
        )

        runtime.close(timeout_seconds=1.0)

        assert runtime._stream_thread is not None
        assert runtime._stream_thread.is_alive() is False
        assert runtime._active_stream_response is None
    finally:
        server.should_exit = True
        server_thread.join(timeout=3.0)
        listen_socket.close()
        if runtime is not None and (
            runtime._stream_thread is None
            or not runtime._stream_thread.is_alive()
        ):
            runtime.close(timeout_seconds=1.0)

    assert server_thread.is_alive() is False


def test_agent_event_delivery_close_is_bounded_and_retryable() -> None:
    """A blocked telemetry destination cannot hide an immortal worker."""

    class _BlockingDestination:
        def __init__(self) -> None:
            self.started = ThreadEvent()
            self.release = ThreadEvent()
            self.events: list[AgentEvent] = []

        def emit(self, event: AgentEvent) -> None:
            self.emit_many([event])

        def emit_many(self, events: list[AgentEvent]) -> None:
            self.started.set()
            self.release.wait()
            self.events.extend(events)

    destination = _BlockingDestination()
    sink = QueuedAgentEventSink(
        destination,
        max_depth=1,
        session_id="blocked-events",
    )
    event = AgentEvent(
        event_id=str(uuid4()),
        session_id="blocked-events",
        event_type="runtime.test",
        level="info",
        source="tests",
        summary="blocked delivery",
    )
    sink.emit(event)
    assert destination.started.wait(timeout=1.0)

    with pytest.raises(
        OrderedDeliveryTimeoutError,
        match="did not stop",
    ):
        sink.close(timeout_seconds=0.01)
    assert sink.worker_alive is True
    with pytest.raises(RuntimeError, match="closed"):
        sink.emit(event)

    destination.release.set()
    sink.close(timeout_seconds=1.0)

    assert sink.worker_alive is False
    assert destination.events == [event]


def test_runtime_close_reports_uncooperative_observation_worker_and_retries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Partial cleanup remains visible until the observation worker exits."""
    runtime = SubjectiveRuntime(
        "http://testserver",
        "blocked-observation-session",
        event_sink=MemoryAgentEventSink(),
        processors=[],
    )
    entered = ThreadEvent()
    release = ThreadEvent()

    def blocked_events(_since: int):
        entered.set()
        release.wait()
        yield "heartbeat", {}

    monkeypatch.setattr(runtime, "iter_observation_events", blocked_events)
    runtime._start_observation_pump()
    assert entered.wait(timeout=1.0)
    assert automatic_gc_suspended()

    with pytest.raises(
        RuntimeError,
        match="observation worker did not stop",
    ):
        runtime.close(timeout_seconds=0.01)

    assert not automatic_gc_suspended()
    release.set()
    runtime.close(timeout_seconds=1.0)

    assert runtime._stream_thread is not None
    assert runtime._stream_thread.is_alive() is False


class _ConnectedRequest:
    """Minimal request stub for direct SSE generator contract tests."""

    async def is_disconnected(self) -> bool:
        """Keep the test subscriber connected until its generator is closed."""
        return False


def _decode_sse_chunk(chunk: str | bytes) -> tuple[str, dict]:
    """Decode one formatted SSE chunk into its event and JSON payload."""
    text = chunk.decode() if isinstance(chunk, bytes) else chunk
    event_name = next(
        line.removeprefix("event: ")
        for line in text.splitlines()
        if line.startswith("event: ")
    )
    data = "\n".join(
        line.removeprefix("data: ")
        for line in text.splitlines()
        if line.startswith("data: ")
    )
    return event_name, json.loads(data)


async def _next_sse_event(response) -> tuple[str, dict]:
    """Read one event from a direct StreamingResponse body iterator."""
    return _decode_sse_chunk(await anext(response.body_iterator))


def test_observation_subscription_race_cancels_losing_wait_task() -> None:
    """Observation SSE waits should not leak the task that did not receive data."""

    async def run_check() -> None:
        winner = BoundedSubscription()
        loser = BoundedSubscription()
        winner.try_enqueue({"event": "winner", "data": {"ok": True}, "id": "winner"})

        before = asyncio.all_tasks()
        result = await event_server._first_subscription_envelope([winner, loser], timeout=0.1)
        await asyncio.sleep(0)
        leaked = [
            task for task in asyncio.all_tasks()
            if task not in before and not task.done()
        ]

        assert result is not None
        assert result["event"] == "winner"
        assert leaked == []

    asyncio.run(run_check())


def test_observation_subscription_replays_more_than_one_page_without_skipping() -> None:
    """Initial SSE replay delivers every retained frame after the requested cursor."""
    _client, session_id, _hero, _monster, _encounter = create_observation_game()
    start_cursor = event_server.get_observation_cursor(
        session_id,
        session_manager=event_server.sim.get_session_manager(),
    )
    for index in range(501):
        append_observation_control_frame(
            session_id,
            ObservationFrame(
                observation_cursor=0,
                frame_type=ObservationFrameType.EVENT,
                source_kind=ObservationSourceKind.CONTROLLER_COMMAND,
                event_type=f"replay_probe_{index}",
            ),
            session_manager=event_server.sim.get_session_manager(),
        )

    async def collect() -> list[tuple[str, dict]]:
        response = await event_server.subscribe_ai_observation(
            _ConnectedRequest(),
            session_id,
            since=start_cursor,
        )
        try:
            return [
                await _next_sse_event(response)
                for _ in range(502)
            ]
        finally:
            await response.body_iterator.aclose()

    events = asyncio.run(collect())

    assert events[0][0] == "sync"
    replay = [payload for name, payload in events[1:] if name == "observation_frame"]
    assert len(replay) == 501
    assert replay[0]["observation_cursor"] == start_cursor + 1
    assert replay[-1]["observation_cursor"] == start_cursor + 501


def test_observation_subscription_rejects_cursor_ahead_of_server() -> None:
    """A future resume cursor fails explicitly instead of silently stalling."""
    client, session_id, _hero, _monster, _encounter = create_observation_game()
    cursor = client.get(
        f"/ai/sessions/{session_id}/observation/snapshot"
    ).json()["observation_cursor"]

    async def read_error() -> tuple[str, dict]:
        response = await event_server.subscribe_ai_observation(
            _ConnectedRequest(),
            session_id,
            since=cursor + 1,
        )
        try:
            return await _next_sse_event(response)
        finally:
            await response.body_iterator.aclose()

    event_name, payload = asyncio.run(read_error())

    assert event_name == "error"
    assert payload["code"] == "observation_cursor_ahead"


def test_observation_subscription_emits_heartbeat_and_no_buffer_headers(
    monkeypatch,
) -> None:
    """An idle subjective stream remains observable and proxy-safe."""
    client, session_id, _hero, _monster, _encounter = create_observation_game()
    snapshot = client.get(
        f"/ai/sessions/{session_id}/observation/snapshot"
    ).json()

    async def immediate_timeout(_subscriptions, *, timeout):
        assert timeout == 10.0
        return None

    monkeypatch.setattr(
        event_server,
        "_first_subscription_envelope",
        immediate_timeout,
    )

    async def read_events() -> tuple[object, tuple[str, dict], tuple[str, dict]]:
        response = await event_server.subscribe_ai_observation(
            _ConnectedRequest(),
            session_id,
            since=snapshot["observation_cursor"],
        )
        try:
            return (
                response,
                await _next_sse_event(response),
                await _next_sse_event(response),
            )
        finally:
            await response.body_iterator.aclose()

    response, sync, heartbeat = asyncio.run(read_events())

    assert sync[0] == "sync"
    assert heartbeat[0] == "heartbeat"
    assert heartbeat[1]["observation_cursor"] == snapshot["observation_cursor"]
    assert response.headers["cache-control"] == "no-cache"
    assert response.headers["x-accel-buffering"] == "no"


def test_engine_projection_publishes_exact_session_subjective_frame() -> None:
    """Engine completions wake one session with the projected frame itself."""
    client, session_id, _hero, _monster, _encounter = create_observation_game()
    snapshot = client.get(f"/ai/sessions/{session_id}/observation/snapshot").json()
    epoch = snapshot["current_epoch"]
    row = _first_affordable_position_row(epoch)
    subscription = observation_wakeup_stream.subscribe(session_id)
    try:
        response = client.post(
            f"/ai/sessions/{session_id}/commands/execute",
            json={
                "command_id": str(uuid4()),
                "actor_uuid": epoch["actor_uuid"],
                "basis_epoch_id": epoch["epoch_id"],
                "row_id": row["row_id"],
            },
        )
        envelope = asyncio.run(asyncio.wait_for(subscription.get(), timeout=1.0))
    finally:
        observation_wakeup_stream.unsubscribe(session_id, subscription)

    assert response.status_code == 200
    assert envelope["event"] == "observation_frame"
    frame = envelope["data"]
    assert isinstance(frame, ObservationFrame)
    assert frame.observation_cursor == snapshot["observation_cursor"] + 1
    assert frame.source_kind in {
        ObservationSourceKind.ENGINE_EVENT,
        ObservationSourceKind.SENSORY_EVENT,
        ObservationSourceKind.COMBAT_LOG,
    }


def test_base_action_batches_passive_event_observers_at_causal_boundary() -> None:
    """One Move retains every event while notifying batch observers once."""
    client, session_id, hero, _monster, _encounter = create_observation_game()
    snapshot = client.get(
        f"/ai/sessions/{session_id}/observation/snapshot"
    ).json()
    epoch = DecisionEpoch.model_validate(snapshot["current_epoch"])
    movement_rows = [
        row
        for row in epoch.affordances.position_actions
        if row.can_afford and row.targets and row.targets[0].path
    ]
    row = max(
        movement_rows,
        key=lambda candidate: len(candidate.targets[0].path),
    )
    target = row.targets[0]
    batches: list[tuple] = []

    def capture_batch(events) -> None:
        batches.append(tuple(events))

    EventQueue.add_on_event_batch_callback(capture_batch)
    try:
        before_cursor = EventQueue.event_cursor()
        result = execute_by_index(hero, row.template_name, target.index)
    finally:
        EventQueue.remove_on_event_batch_callback(capture_batch)

    stored = tuple(event for _index, event in EventQueue.iter_events_since(before_cursor))
    assert result is not None
    assert len(stored) > 1
    assert len(batches) == 1
    assert batches[0] == stored
    assert any(event.phase == EventPhase.COMPLETION for event in batches[0])


def test_passive_event_batch_observer_receives_standalone_event_immediately() -> None:
    """An event outside an action remains immediately observable."""
    EventQueue.reset()
    batches: list[tuple[Event, ...]] = []

    def capture_batch(events: Sequence[Event]) -> None:
        batches.append(tuple(events))

    EventQueue.add_on_event_batch_callback(capture_batch)
    try:
        event = EventQueue.register(Event(
            source_entity_uuid=uuid4(),
            event_type=EventType.BASE_ACTION,
            phase=EventPhase.COMPLETION,
            use_register=False,
        ))
    finally:
        EventQueue.remove_on_event_batch_callback(capture_batch)

    assert batches == [(event,)]


def test_nested_passive_event_batches_flush_once_in_storage_order() -> None:
    """Nested causal scopes share the outer action's ordered event batch."""
    EventQueue.reset()
    batches: list[tuple[Event, ...]] = []

    def capture_batch(events: Sequence[Event]) -> None:
        batches.append(tuple(events))

    EventQueue.add_on_event_batch_callback(capture_batch)
    try:
        with EventQueue.batch_on_event_callbacks():
            first = EventQueue.register(Event(
                source_entity_uuid=uuid4(),
                event_type=EventType.BASE_ACTION,
                phase=EventPhase.DECLARATION,
                use_register=False,
            ))
            with EventQueue.batch_on_event_callbacks():
                second = EventQueue.register(Event(
                    source_entity_uuid=first.source_entity_uuid,
                    event_type=EventType.BASE_ACTION,
                    phase=EventPhase.COMPLETION,
                    use_register=False,
                ))
    finally:
        EventQueue.remove_on_event_batch_callback(capture_batch)

    assert batches == [(first, second)]


def test_completion_sequence_preserves_events_and_notifies_projection_once() -> None:
    """One derived-state cause stores every completion before one projection pass."""
    EventQueue.reset()
    immediate: list[Event] = []
    sequences: list[tuple[Event, ...]] = []

    def capture_event(event: Event) -> None:
        immediate.append(event)

    def capture_sequence(events: Sequence[Event]) -> None:
        sequences.append(tuple(events))

    EventQueue.add_on_event_callback(capture_event)
    EventQueue.add_on_event_sequence_callback(capture_sequence)
    events = (
        Event(
            source_entity_uuid=uuid4(),
            event_type=EventType.SENSORY_UPDATE,
            phase=EventPhase.COMPLETION,
            use_register=False,
        ),
        Event(
            source_entity_uuid=uuid4(),
            event_type=EventType.SENSORY_UPDATE,
            phase=EventPhase.COMPLETION,
            use_register=False,
        ),
    )
    try:
        stored = EventQueue.register_completion_sequence(events)
    finally:
        EventQueue.remove_on_event_callback(capture_event)
        EventQueue.remove_on_event_sequence_callback(capture_sequence)

    assert stored == events
    assert immediate == list(events)
    assert sequences == [events]
    assert tuple(EventQueue._all_events) == events


def test_subjective_projector_defers_delivery_but_not_event_time_capture(monkeypatch) -> None:
    """Frames persist immediately while action-scoped wakeups wait to flush."""
    client, session_id, hero, _monster, _encounter = create_observation_game()
    client.get(f"/ai/sessions/{session_id}/observation/snapshot")
    published: list[tuple[str, ObservationFrame]] = []

    def capture_publish(published_session_id: str, frame: ObservationFrame) -> None:
        published.append((published_session_id, frame))

    monkeypatch.setattr(
        observation_projector.observation_wakeup_stream,
        "publish",
        capture_publish,
    )
    with EventQueue.batch_on_event_callbacks():
        completion = EventQueue.register(SensoryUpdateEvent(
            source_entity_uuid=hero.uuid,
            target_entity_uuid=hero.uuid,
            observer_uuid=hero.uuid,
            cause_event_uuid=uuid4(),
            update_reason=SensoryUpdateReason.SPATIAL,
            visible_cells_added=[(5, 5)],
            phase=EventPhase.COMPLETION,
            use_register=False,
        ))
        cached_frames = observation_projector._projection_cache[session_id].frames
        assert cached_frames[-1].event_uuid == str(completion.uuid)
        assert published == []

    assert [(published_session_id, frame.event_uuid) for published_session_id, frame in published] == [
        (session_id, str(completion.uuid)),
    ]


def test_damage_projection_defers_until_action_batch_boundary(monkeypatch) -> None:
    """HP-only events project once at the action boundary, not per child event."""
    client, session_id, hero, monster, _encounter = create_observation_game()
    client.get(f"/ai/sessions/{session_id}/observation/snapshot")
    published: list[tuple[str, ObservationFrame]] = []
    initial_frame_count = len(observation_projector._projection_cache[session_id].frames)

    def capture_publish(published_session_id: str, frame: ObservationFrame) -> None:
        published.append((published_session_id, frame))

    monkeypatch.setattr(
        observation_projector.observation_wakeup_stream,
        "publish",
        capture_publish,
    )
    with EventQueue.batch_on_event_callbacks():
        completion = EventQueue.register(Event(
            source_entity_uuid=hero.uuid,
            target_entity_uuid=monster.uuid,
            event_type=EventType.DAMAGE_APPLIED,
            phase=EventPhase.COMPLETION,
            use_register=False,
        ))
        assert len(observation_projector._projection_cache[session_id].frames) == initial_frame_count
        assert published == []

    cached_frames = observation_projector._projection_cache[session_id].frames
    assert len(cached_frames) == initial_frame_count + 1
    assert cached_frames[-1].event_uuid == str(completion.uuid)
    assert [(published_session_id, frame.event_uuid) for published_session_id, frame in published] == [
        (session_id, str(completion.uuid)),
    ]


def test_subjective_sse_does_not_subscribe_to_global_objective_stream(monkeypatch) -> None:
    """AI live delivery uses only the session-subjective projection queue."""
    _client, session_id, _hero, _monster, _encounter = create_observation_game()

    def fail_objective_subscription(*_args, **_kwargs):
        pytest.fail("subjective SSE subscribed to the global objective stream")

    monkeypatch.setattr(event_server.event_stream, "subscribe", fail_objective_subscription)

    class ConnectedRequest:
        async def is_disconnected(self) -> bool:
            return False

    async def read_sync_event() -> str:
        response = await event_server.subscribe_ai_observation(
            ConnectedRequest(),  # type: ignore[arg-type]
            session_id,
        )
        iterator = cast(AsyncGenerator[str | bytes, None], response.body_iterator)
        first = await anext(iterator)
        await iterator.aclose()
        return first.decode() if isinstance(first, bytes) else first

    first_event = asyncio.run(read_sync_event())

    assert "event: sync" in first_event


def test_stale_command_emits_subjective_result_without_engine_mutation() -> None:
    """Stale commands are controller-protocol events, not objective game events."""
    client, session_id, _hero, _monster, _encounter = create_observation_game()
    snapshot = client.get(f"/ai/sessions/{session_id}/observation/snapshot").json()
    epoch = snapshot["current_epoch"]
    row = _first_affordable_position_row(epoch)
    command_id = str(uuid4())
    engine_cursor_before = EventQueue.event_cursor()

    response = client.post(
        f"/ai/sessions/{session_id}/commands/execute",
        json={
            "command_id": command_id,
            "actor_uuid": epoch["actor_uuid"],
            "basis_epoch_id": f"{epoch['epoch_id']}:stale",
            "row_id": row["row_id"],
        },
    )
    frames = client.get(
        f"/ai/sessions/{session_id}/observation/frames",
        params={"since": snapshot["observation_cursor"], "limit": 0},
    ).json()["frames"]

    assert response.status_code == 200
    assert response.json()["status"] == "stale"
    assert response.json()["resync_required"] is False
    assert EventQueue.event_cursor() == engine_cursor_before
    command_frames = [frame for frame in frames if frame["frame_type"] == "command_result"]
    epoch_frames = [frame for frame in frames if frame["frame_type"] == "decision_epoch"]
    assert command_frames
    assert command_frames[-1]["source_kind"] == "controller_command"
    assert command_frames[-1]["source_command_id"] == command_id
    assert command_frames[-1]["command_result"]["command_id"] == command_id
    assert command_frames[-1]["source_event_cursor"] is None
    assert epoch_frames
    assert epoch_frames[-1]["source_kind"] == "decision_epoch"
    assert epoch_frames[-1]["source_command_id"] == command_id


def test_published_epoch_survives_control_cursor_advancement() -> None:
    """A published decision epoch remains valid after its control frame advances the cursor."""
    client, session_id, _hero, _monster, _encounter = create_observation_game()
    epoch = event_server._publish_decision_epoch_for_session(
        session_id,
        event_server.DecisionEpochReason.TURN_START,
    )
    assert epoch is not None
    snapshot = client.get(f"/ai/sessions/{session_id}/observation/snapshot").json()
    row = _first_affordable_position_row(epoch.model_dump(mode="json"))
    command_id = str(uuid4())

    response = client.post(
        f"/ai/sessions/{session_id}/commands/execute",
        json={
            "command_id": command_id,
            "actor_uuid": epoch.actor_uuid,
            "basis_epoch_id": epoch.epoch_id,
            "row_id": row["row_id"],
        },
    )

    assert snapshot["observation_cursor"] > epoch.basis_observation_cursor
    assert response.status_code == 200
    assert response.json()["status"] == "accepted"


def test_active_epoch_publication_skips_human_sessions(monkeypatch) -> None:
    """Human turns should not publish AI decision epochs during advancement."""
    _client, session_id, _hero, _monster, _encounter = create_observation_game()
    session = event_server.sim.get_session_manager().get_session(UUID(session_id))
    assert session is not None
    session.player_type = PlayerType.HUMAN
    event_server._current_epoch_by_session.pop(session_id, None)
    calls = 0
    original_build = event_server._build_decision_epoch

    def wrapped_build(*args, **kwargs):
        nonlocal calls
        calls += 1
        return original_build(*args, **kwargs)

    monkeypatch.setattr(event_server, "_build_decision_epoch", wrapped_build)
    timing = event_server._ServerCommandTiming("advance")

    epoch = event_server._publish_decision_epoch_for_active_session(
        event_server.DecisionEpochReason.TURN_START,
        timing=timing,
    )

    assert epoch is None
    assert calls == 0
    assert "advance.publish_active_epoch.skip_human_session_ms" in timing.payload()["phases"]


def test_active_epoch_publication_skips_unwatched_codex_sessions(monkeypatch) -> None:
    """Unwatched Codex turns should lazy-build epochs through snapshots."""
    client, session_id, _hero, _monster, _encounter = create_observation_game()
    session = event_server.sim.get_session_manager().get_session(UUID(session_id))
    assert session is not None
    session.player_type = PlayerType.CODEX
    event_server._current_epoch_by_session.pop(session_id, None)
    calls = 0
    original_build = event_server._build_decision_epoch

    def wrapped_build(*args, **kwargs):
        nonlocal calls
        calls += 1
        return original_build(*args, **kwargs)

    monkeypatch.setattr(event_server, "_build_decision_epoch", wrapped_build)
    timing = event_server._ServerCommandTiming("advance")

    epoch = event_server._publish_decision_epoch_for_active_session(
        event_server.DecisionEpochReason.TURN_START,
        timing=timing,
    )
    snapshot = client.get(f"/ai/sessions/{session_id}/observation/snapshot").json()

    assert epoch is None
    assert calls == 1
    assert snapshot["current_epoch"] is not None
    assert "advance.publish_active_epoch.skip_unwatched_codex_session_ms" in timing.payload()["phases"]


def test_active_epoch_publication_persists_for_live_takeover_without_subscriber(monkeypatch) -> None:
    """A live takeover must not lose its next epoch to the subscriber race."""
    _client, session_id, hero, _monster, encounter = create_observation_game()
    game = event_server.sim.game
    assert game is not None
    session = event_server.sim.get_session_manager().get_session(UUID(session_id))
    assert session is not None
    session.player_type = PlayerType.CODEX
    event_server.ai_takeover_manager.claim(
        encounter=encounter,
        game=game,
        session_manager=event_server.sim.get_session_manager(),
        faction="heroes",
        session_id=session.session_id,
        name="Attached Codex",
    )
    event_server._current_epoch_by_session.pop(session_id, None)
    calls = 0
    original_build = event_server._build_decision_epoch

    def wrapped_build(*args, **kwargs):
        nonlocal calls
        calls += 1
        return original_build(*args, **kwargs)

    monkeypatch.setattr(event_server, "_build_decision_epoch", wrapped_build)
    timing = event_server._ServerCommandTiming("advance")

    epoch = event_server._publish_decision_epoch_for_active_session(
        event_server.DecisionEpochReason.TURN_START,
        timing=timing,
    )

    assert epoch is not None
    assert epoch.actor_uuid == str(hero.uuid)
    assert calls == 1
    assert "advance.publish_active_epoch.skip_unwatched_codex_session_ms" not in timing.payload()["phases"]


def test_epoch_clear_for_previous_actor_does_not_invalidate_current_server_epoch() -> None:
    """The server suppresses a stale clear instead of asking clients to repair it."""
    client, session_id, _hero, _monster, _encounter = create_observation_game()
    epoch = event_server._publish_decision_epoch_for_session(
        session_id,
        event_server.DecisionEpochReason.TURN_START,
    )
    assert epoch is not None
    before = client.get(
        f"/ai/sessions/{session_id}/observation/snapshot"
    ).json()["observation_cursor"]

    event_server._publish_epoch_clear_for_session(
        session_id,
        "turn_ended",
        source_command_id=str(uuid4()),
        actor_uuid=str(uuid4()),
    )
    snapshot = client.get(f"/ai/sessions/{session_id}/observation/snapshot").json()
    frames = client.get(
        f"/ai/sessions/{session_id}/observation/frames",
        params={"since": before, "limit": 0},
    ).json()["frames"]

    assert snapshot["current_epoch"]["epoch_id"] == epoch.epoch_id
    assert frames == []


def test_published_epoch_timing_breaks_down_available_action_discovery() -> None:
    """Decision-epoch timing exposes the action-discovery phases agents wait on."""
    _client, session_id, _hero, _monster, _encounter = create_observation_game()
    timing = event_server._ServerCommandTiming("epoch", diagnostics_enabled=True)

    epoch = event_server._publish_decision_epoch_for_session(
        session_id,
        event_server.DecisionEpochReason.TURN_START,
        timing=timing,
    )
    phases = timing.payload()["phases"]

    assert epoch is not None
    assert "publish.followup_epoch.get_available_actions_ms" in phases
    assert "publish.followup_epoch.available_actions.potential_targets_ms" in phases
    assert "publish.followup_epoch.available_actions.collect_entity_actions_ms" in phases
    assert "publish.followup_epoch.available_actions.entity_actions.target_pool_total_ms" in phases
    assert "publish.followup_epoch.available_actions.entity_actions.validate_targets_total_ms" in phases
    assert "publish.followup_epoch.available_actions.entity_actions.make_info_total_ms" in phases
    assert "publish.followup_epoch.available_actions.collect_path_actions_ms" in phases
    assert "publish.followup_epoch.build_capabilities.registered_variants_ms" in phases
    assert "publish.followup_epoch.build_capabilities.inventory_sources_ms" in phases
    assert "publish.followup_epoch.build_capabilities.metadata_and_models_ms" in phases
    assert "publish.followup_epoch.build_capabilities.total_ms" in phases
    assert "publish.followup_epoch.action_economy.actions_normalized_score_ms" in phases
    assert "publish.followup_epoch.action_economy.meaningful_rows_ms" in phases
    assert "publish.followup_epoch.action_economy.construct_model_ms" in phases
    assert "publish.followup_epoch.serialize_available_actions_ms" not in phases


def test_position_aoe_action_lifecycle_timing_records_convolution_phases() -> None:
    """A real area spell exposes the action lifecycle inside execute-by-index."""
    arena = create_ai_validation_arena("line_aoe_corridor")
    hero = arena.hero
    hero.update_entity_senses(max_distance=20)
    actions = hero.get_available_actions()
    fireball = next(
        row
        for row in actions.position_actions
        if row.template_name == "Fireball__slot_3"
    )
    target = max(fireball.valid_targets, key=lambda candidate: candidate.affected_count or 0)
    phases: dict[str, float] = {}

    def record_phase(phase: str, started_at: float) -> None:
        phases[phase] = phases.get(phase, 0.0) + ((time.perf_counter() - started_at) * 1000)

    token = set_action_timing_recorder(record_phase)
    try:
        event = execute_by_index(hero, fireball.template_name, target.index, available=actions)
    finally:
        reset_action_timing_recorder(token)

    assert event is not None
    assert not event.canceled
    assert target.affected_count == 4
    assert "base_action.check_costs_ms" in phases
    assert "base_action.create_declaration_event_ms" in phases
    assert "base_action.validate_ms" in phases
    assert "base_action.resolve_convolution_targets_ms" in phases
    assert "base_action.convolution_apply_targets_ms" in phases
    assert "base_action.convolution_target_apply_ms" in phases
    assert "base_action.convolution_completion_event_ms" in phases
    assert "base_action.apply_costs_ms" in phases
    assert "base_action.apply_total_ms" in phases
    assert "spell.fireball.saving_throw_ms" in phases
    assert "spell.fireball.receive_damage_ms" in phases
    assert "spell.fireball.completion_event_ms" in phases


def test_accepted_command_publishes_result_then_followup_epoch() -> None:
    """Explicit diagnostics retain deep action and projection phase timing."""
    client, session_id, _hero, _monster, _encounter = create_observation_game()
    snapshot = client.get(f"/ai/sessions/{session_id}/observation/snapshot").json()
    epoch = snapshot["current_epoch"]
    row = _first_affordable_position_row(epoch)
    command_id = str(uuid4())

    response = client.post(
        f"/ai/sessions/{session_id}/commands/execute",
        json={
            "command_id": command_id,
            "actor_uuid": epoch["actor_uuid"],
            "basis_epoch_id": epoch["epoch_id"],
            "row_id": row["row_id"],
            "prefer_safe": True,
            "include_diagnostics": True,
        },
    )
    frames = client.get(
        f"/ai/sessions/{session_id}/observation/frames",
        params={"since": snapshot["observation_cursor"], "limit": 0},
    ).json()["frames"]

    assert response.status_code == 200
    ack = response.json()
    assert ack["status"] == "accepted"
    assert ack["command_id"] == command_id
    assert ack["resync_required"] is False
    assert ack["payload"]["server_timing"]["command_type"] == "execute"
    assert "build.current_epoch_ms" in ack["payload"]["server_timing"]["phases"]
    command_frame = next(
        frame for frame in frames
        if frame["frame_type"] == "command_result" and frame["source_command_id"] == command_id
    )
    followup_epoch = next(
        frame for frame in frames
        if frame["frame_type"] == "decision_epoch" and frame["source_command_id"] == command_id
    )
    assert command_frame["observation_cursor"] < followup_epoch["observation_cursor"]
    assert command_frame["command_result"]["status"] == "accepted"
    assert command_frame["command_result"]["accepted_at_observation_cursor"] == command_frame["observation_cursor"]
    action_result = command_frame["command_result"]["payload"]
    assert "state" not in action_result
    assert "available_actions" not in action_result
    assert action_result["server_timing"]["command_type"] == "execute"
    assert action_result["action_server_timing"]["command_type"] == "action_execute"
    assert "execute_by_index_ms" in action_result["action_server_timing"]["phases"]
    assert "final.entity_hp_ms" not in action_result["action_server_timing"]["phases"]
    assert "final.action_cursor_fields_ms" in action_result["action_server_timing"]["phases"]
    assert "build_action_result_model_ms" in action_result["action_server_timing"]["phases"]
    assert "execute_by_index.grid.compute_paths.dijkstra_total_ms" in action_result["action_server_timing"]["phases"]
    assert "execute_by_index.grid.compute_paths.can_enter_ms" in action_result["action_server_timing"]["phases"]
    assert "execute_by_index.sensory_callback.handle_spatial_event_ms" in action_result["action_server_timing"]["phases"]
    assert "execute_by_index.sensory_callback.emit_update_ms" in action_result["action_server_timing"]["phases"]
    assert "execute_by_index.event_queue.store.total_ms" in action_result["action_server_timing"]["phases"]
    action_timing = action_result["action_server_timing"]
    store_phase = "execute_by_index.event_queue.store.total_ms"
    assert action_timing["phase_counts"][store_phase] > 1
    assert action_timing["phase_max_ms"][store_phase] <= action_timing["phases"][store_phase]
    assert any(
        phase.startswith("execute_by_index.event_queue.pre_completion.callback.SpatialSensesSystem")
        for phase in action_timing["phase_counts"]
    )
    assert "command_result" not in command_frame["patches"][0]["data"]
    assert command_frame["patches"][0]["data"]["command_id"] == command_id
    assert followup_epoch["decision_epoch"] is not None
    assert followup_epoch["decision_epoch"]["reason"] == "action_completed"
    assert followup_epoch["decision_epoch"]["basis_observation_cursor"] == command_frame["observation_cursor"]
    assert "decision_epoch" not in followup_epoch["patches"][0]["data"]
    assert followup_epoch["patches"][0]["data"]["epoch_id"] == followup_epoch["decision_epoch"]["epoch_id"]
    assert all(
        frame["decision_epoch"] is None
        for frame in frames
        if frame["frame_type"] != "decision_epoch"
    )


def test_command_rejects_extra_targets_outside_affordance_before_engine_execution() -> None:
    """Direct controller input cannot add targets absent from the selected row."""
    client, session_id, hero, _monster, _encounter = create_observation_game()
    snapshot = client.get(f"/ai/sessions/{session_id}/observation/snapshot").json()
    epoch = snapshot["current_epoch"]
    row = _first_affordable_position_row(epoch)
    position_before = hero.position

    response = client.post(
        f"/ai/sessions/{session_id}/commands/execute",
        json={
            "command_id": str(uuid4()),
            "actor_uuid": epoch["actor_uuid"],
            "basis_epoch_id": epoch["epoch_id"],
            "row_id": row["row_id"],
            "extra_target_uuids": [str(uuid4())],
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == "rejected"
    assert response.json()["payload"]["code"] == "invalid_target_allocation"
    assert hero.position == position_before


def test_command_never_falls_back_to_name_lookup_without_epoch_authority() -> None:
    """Loss of private row binding makes the command stale without engine mutation."""
    client, session_id, hero, _monster, _encounter = create_observation_game()
    snapshot = client.get(f"/ai/sessions/{session_id}/observation/snapshot").json()
    epoch = snapshot["current_epoch"]
    row = _first_affordable_position_row(epoch)
    position_before = hero.position
    event_server._execution_authority_by_epoch_id.pop(epoch["epoch_id"])

    response = client.post(
        f"/ai/sessions/{session_id}/commands/execute",
        json={
            "command_id": str(uuid4()),
            "actor_uuid": epoch["actor_uuid"],
            "basis_epoch_id": epoch["epoch_id"],
            "row_id": row["row_id"],
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == "stale"
    assert response.json()["resync_required"] is True
    assert response.json()["payload"]["code"] == "execution_authority_unavailable"
    assert hero.position == position_before


def test_normal_command_uses_coarse_timing_without_deep_probe_overhead() -> None:
    """Normal controller commands stay observable without instrumenting inner loops."""
    client, session_id, _hero, _monster, _encounter = create_observation_game()
    snapshot = client.get(f"/ai/sessions/{session_id}/observation/snapshot").json()
    epoch = snapshot["current_epoch"]
    row = _first_affordable_position_row(epoch)
    command_id = str(uuid4())

    response = client.post(
        f"/ai/sessions/{session_id}/commands/execute",
        json={
            "command_id": command_id,
            "actor_uuid": epoch["actor_uuid"],
            "basis_epoch_id": epoch["epoch_id"],
            "row_id": row["row_id"],
            "prefer_safe": True,
        },
    )
    frames = client.get(
        f"/ai/sessions/{session_id}/observation/frames",
        params={"since": snapshot["observation_cursor"], "limit": 0},
    ).json()["frames"]

    assert response.status_code == 200
    ack_timing = response.json()["payload"]["server_timing"]
    assert ack_timing["command_type"] == "execute"
    assert "build.current_epoch_ms" in ack_timing["phases"]
    assert not any(
        phase.startswith("publish.followup_epoch.available_actions.")
        for phase in ack_timing["phases"]
    )
    command_frame = next(
        frame
        for frame in frames
        if frame["frame_type"] == "command_result"
        and frame["source_command_id"] == command_id
    )
    action_result = command_frame["command_result"]["payload"]

    assert action_result["server_timing"]["command_type"] == "execute"
    assert "action_server_timing" not in action_result


def test_runtime_command_followup_ignores_initial_stream_sync(monkeypatch) -> None:
    """An HTTP ack can precede SSE frames without sync forcing a resync."""
    client, session_id, _hero, _monster, _encounter = create_observation_game()
    snapshot = client.get(f"/ai/sessions/{session_id}/observation/snapshot").json()
    epoch = snapshot["current_epoch"]
    command_id = str(uuid4())
    result_payload = CommandResult(
        status=CommandResultStatus.ACCEPTED,
        command_id=command_id,
        session_id=session_id,
        actor_uuid=epoch["actor_uuid"],
        requested_epoch_id=epoch["epoch_id"],
        current_epoch_id=None,
        row_id="position|Move|pos=1,1",
        message="stream accepted",
        resync_required=False,
        accepted_at_observation_cursor=snapshot["observation_cursor"] + 1,
    )
    command_frame = ObservationFrame(
        observation_cursor=snapshot["observation_cursor"] + 1,
        frame_type=ObservationFrameType.COMMAND_RESULT,
        source_kind=ObservationSourceKind.CONTROLLER_COMMAND,
        source_command_id=command_id,
        command_result=result_payload,
    )
    followup_epoch_payload = dict(epoch)
    followup_epoch_payload.update({
        "epoch_id": str(uuid4()),
        "epoch_index": epoch["epoch_index"] + 1,
        "basis_observation_cursor": snapshot["observation_cursor"] + 1,
        "reason": "action_completed",
    })
    followup_frame = ObservationFrame(
        observation_cursor=snapshot["observation_cursor"] + 2,
        frame_type=ObservationFrameType.DECISION_EPOCH,
        source_kind=ObservationSourceKind.DECISION_EPOCH,
        source_command_id=command_id,
        decision_epoch=DecisionEpoch.model_validate(followup_epoch_payload),
    )
    sink = MemoryAgentEventSink()
    runtime = SubjectiveRuntime("http://testserver", session_id, event_sink=sink, processors=[])
    runtime.store.load_snapshot(snapshot)
    resync_calls = []

    def fail_resync():
        resync_calls.append(True)
        raise AssertionError("sync during command follow-up should not resync")

    monkeypatch.setattr(runtime, "resync", fail_resync)
    try:
        ack = CommandResult(
            status=CommandResultStatus.ACCEPTED,
            command_id=command_id,
            session_id=session_id,
            actor_uuid=epoch["actor_uuid"],
            requested_epoch_id=epoch["epoch_id"],
            row_id="position|Move|pos=1,1",
            message="http ack",
            resync_required=False,
        )
        with runtime._state_changed:
            runtime.store.register_pending_command(command_id, ack)
        events, connection_cursors = _start_queue_backed_observation_pump(
            monkeypatch,
            runtime,
            sync_cursor=snapshot["observation_cursor"],
        )
        events.put(("observation_frame", command_frame.model_dump(mode="json")))
        events.put(("observation_frame", followup_frame.model_dump(mode="json")))
        result = runtime._wait_for_command_followup(command_id, ack)
    finally:
        runtime.close()

    assert not resync_calls
    assert connection_cursors == [snapshot["observation_cursor"]]
    assert result.message == "stream accepted"
    assert runtime.store.world is not None
    assert runtime.store.world.observation_cursor == snapshot["observation_cursor"] + 2
    assert any(event.event_type == "stream.synced" for event in sink.events)


def test_runtime_command_followup_uses_subjective_stream_without_history_poll(
    monkeypatch,
) -> None:
    """SSE frames may arrive before their HTTP ack without any history poll."""
    client, session_id, _hero, _monster, _encounter = create_observation_game()
    snapshot = client.get(f"/ai/sessions/{session_id}/observation/snapshot").json()
    epoch = snapshot["current_epoch"]
    command_id = str(uuid4())
    result_payload = CommandResult(
        status=CommandResultStatus.ACCEPTED,
        command_id=command_id,
        session_id=session_id,
        actor_uuid=epoch["actor_uuid"],
        requested_epoch_id=epoch["epoch_id"],
        current_epoch_id=None,
        row_id="position|Move|pos=1,1",
        message="persisted accepted",
        resync_required=False,
        accepted_at_observation_cursor=snapshot["observation_cursor"] + 1,
    )
    command_frame = ObservationFrame(
        observation_cursor=snapshot["observation_cursor"] + 1,
        frame_type=ObservationFrameType.COMMAND_RESULT,
        source_kind=ObservationSourceKind.CONTROLLER_COMMAND,
        source_command_id=command_id,
        command_result=result_payload,
    )
    followup_epoch_payload = dict(epoch)
    followup_epoch_payload.update({
        "epoch_id": str(uuid4()),
        "epoch_index": epoch["epoch_index"] + 1,
        "basis_observation_cursor": snapshot["observation_cursor"] + 1,
        "reason": "action_completed",
    })
    followup_frame = ObservationFrame(
        observation_cursor=snapshot["observation_cursor"] + 2,
        frame_type=ObservationFrameType.DECISION_EPOCH,
        source_kind=ObservationSourceKind.DECISION_EPOCH,
        source_command_id=command_id,
        decision_epoch=DecisionEpoch.model_validate(followup_epoch_payload),
    )
    runtime = SubjectiveRuntime("http://testserver", session_id, event_sink=MemoryAgentEventSink(), processors=[])
    runtime.store.load_snapshot(snapshot)

    try:
        ack = CommandResult(
            status=CommandResultStatus.ACCEPTED,
            command_id=command_id,
            session_id=session_id,
            actor_uuid=epoch["actor_uuid"],
            requested_epoch_id=epoch["epoch_id"],
            row_id="position|Move|pos=1,1",
            message="http ack",
            resync_required=False,
        )
        with runtime._state_changed:
            runtime.store.register_pending_command(
                command_id,
                actor_uuid=epoch["actor_uuid"],
                requested_epoch_id=epoch["epoch_id"],
                row_id="position|Move|pos=1,1",
            )
        events, connection_cursors = _start_queue_backed_observation_pump(
            monkeypatch,
            runtime,
            sync_cursor=snapshot["observation_cursor"],
        )
        events.put(("observation_frame", command_frame.model_dump(mode="json")))
        events.put(("observation_frame", followup_frame.model_dump(mode="json")))
        deadline = time.monotonic() + 1.0
        while (
            runtime.store.world is not None
            and runtime.store.world.observation_cursor < followup_frame.observation_cursor
            and time.monotonic() < deadline
        ):
            time.sleep(0.001)
        with runtime._state_changed:
            runtime.store.register_pending_command(command_id, ack)
            runtime._state_changed.notify_all()
        result = runtime._wait_for_command_followup(command_id, ack)
    finally:
        runtime.close()

    assert connection_cursors == [snapshot["observation_cursor"]]
    assert result.message == "persisted accepted"
    assert runtime.store.world is not None
    assert runtime.store.world.observation_cursor == snapshot["observation_cursor"] + 2


@pytest.mark.parametrize(
    ("status", "reason"),
    [
        (CommandResultStatus.REJECTED, "action_rejected"),
        (CommandResultStatus.STALE, "action_stale"),
    ],
)
def test_runtime_nonaccepted_command_waits_for_correlated_replacement_epoch(
    monkeypatch,
    status: CommandResultStatus,
    reason: str,
) -> None:
    """Rejected and stale results require their exactly correlated control frame."""
    client, session_id, _hero, _monster, _encounter = create_observation_game()
    snapshot = client.get(f"/ai/sessions/{session_id}/observation/snapshot").json()
    epoch = snapshot["current_epoch"]
    command_id = str(uuid4())
    result = CommandResult(
        status=status,
        command_id=command_id,
        session_id=session_id,
        actor_uuid=epoch["actor_uuid"],
        requested_epoch_id=epoch["epoch_id"],
        current_epoch_id=epoch["epoch_id"],
        row_id="position|Move|pos=1,1",
        message="movement rejected",
        resync_required=False,
        accepted_at_observation_cursor=snapshot["observation_cursor"] + 1,
    )
    command_frame = ObservationFrame(
        observation_cursor=snapshot["observation_cursor"] + 1,
        frame_type=ObservationFrameType.COMMAND_RESULT,
        source_kind=ObservationSourceKind.CONTROLLER_COMMAND,
        source_command_id=command_id,
        command_result=result,
    )
    uncorrelated_epoch_payload = dict(epoch)
    uncorrelated_epoch_payload.update({
        "epoch_id": str(uuid4()),
        "epoch_index": epoch["epoch_index"] + 1,
        "basis_observation_cursor": snapshot["observation_cursor"] + 1,
        "reason": "resync",
    })
    uncorrelated_frame = ObservationFrame(
        observation_cursor=snapshot["observation_cursor"] + 2,
        frame_type=ObservationFrameType.DECISION_EPOCH,
        source_kind=ObservationSourceKind.DECISION_EPOCH,
        source_command_id=None,
        decision_epoch=DecisionEpoch.model_validate(uncorrelated_epoch_payload),
    )
    replacement_epoch_payload = dict(epoch)
    replacement_epoch_payload.update({
        "epoch_id": str(uuid4()),
        "epoch_index": epoch["epoch_index"] + 2,
        "basis_observation_cursor": snapshot["observation_cursor"] + 2,
        "reason": reason,
    })
    replacement_frame = ObservationFrame(
        observation_cursor=snapshot["observation_cursor"] + 3,
        frame_type=ObservationFrameType.DECISION_EPOCH,
        source_kind=ObservationSourceKind.DECISION_EPOCH,
        source_command_id=command_id,
        decision_epoch=DecisionEpoch.model_validate(replacement_epoch_payload),
    )
    runtime = SubjectiveRuntime(
        "http://testserver",
        session_id,
        event_sink=MemoryAgentEventSink(),
        processors=[],
    )
    runtime.store.load_snapshot(snapshot)
    try:
        with runtime._state_changed:
            runtime.store.register_pending_command(command_id, result)
        events, connection_cursors = _start_queue_backed_observation_pump(
            monkeypatch,
            runtime,
            sync_cursor=snapshot["observation_cursor"],
        )
        events.put(("observation_frame", command_frame.model_dump(mode="json")))
        events.put(("observation_frame", uncorrelated_frame.model_dump(mode="json")))
        events.put(("observation_frame", replacement_frame.model_dump(mode="json")))
        observed = runtime._wait_for_command_followup(command_id, result)
        deadline = time.monotonic() + 1.0
        while (
            runtime.store.world is not None
            and runtime.store.world.observation_cursor < replacement_frame.observation_cursor
            and time.monotonic() < deadline
        ):
            time.sleep(0.001)
    finally:
        runtime.close()

    assert connection_cursors == [snapshot["observation_cursor"]]
    assert observed.message == "movement rejected"
    assert runtime.store.world is not None
    assert runtime.store.world.observation_cursor == replacement_frame.observation_cursor
    assert runtime.store.world.current_epoch is not None
    assert runtime.store.world.current_epoch.epoch_id == replacement_epoch_payload["epoch_id"]


def test_runtime_command_followup_batches_stream_frame_processors(monkeypatch) -> None:
    """The SSE pump applies all frames but avoids per-frame processor churn."""
    client, session_id, _hero, _monster, _encounter = create_observation_game()
    snapshot = client.get(f"/ai/sessions/{session_id}/observation/snapshot").json()
    epoch = snapshot["current_epoch"]
    command_id = str(uuid4())
    noise_frames = [
        ObservationFrame(
            observation_cursor=snapshot["observation_cursor"] + 1,
            frame_type=ObservationFrameType.EVENT,
            source_kind=ObservationSourceKind.ENGINE_EVENT,
            event_type="sensory_update",
        ),
        ObservationFrame(
            observation_cursor=snapshot["observation_cursor"] + 2,
            frame_type=ObservationFrameType.EVENT,
            source_kind=ObservationSourceKind.ENGINE_EVENT,
            event_type="movement",
        ),
    ]
    result_payload = CommandResult(
        status=CommandResultStatus.ACCEPTED,
        command_id=command_id,
        session_id=session_id,
        actor_uuid=epoch["actor_uuid"],
        requested_epoch_id=epoch["epoch_id"],
        current_epoch_id=None,
        row_id="position|Move|pos=1,1",
        message="batched accepted",
        resync_required=False,
        accepted_at_observation_cursor=snapshot["observation_cursor"] + 3,
    )
    command_frame = ObservationFrame(
        observation_cursor=snapshot["observation_cursor"] + 3,
        frame_type=ObservationFrameType.COMMAND_RESULT,
        source_kind=ObservationSourceKind.CONTROLLER_COMMAND,
        source_command_id=command_id,
        command_result=result_payload,
    )
    final_noise = ObservationFrame(
        observation_cursor=snapshot["observation_cursor"] + 4,
        frame_type=ObservationFrameType.EVENT,
        source_kind=ObservationSourceKind.ENGINE_EVENT,
        event_type="combat_log",
    )
    followup_epoch_payload = dict(epoch)
    followup_epoch_payload.update({
        "epoch_id": str(uuid4()),
        "epoch_index": epoch["epoch_index"] + 1,
        "basis_observation_cursor": snapshot["observation_cursor"] + 4,
        "reason": "action_completed",
    })
    followup_frame = ObservationFrame(
        observation_cursor=snapshot["observation_cursor"] + 5,
        frame_type=ObservationFrameType.DECISION_EPOCH,
        source_kind=ObservationSourceKind.DECISION_EPOCH,
        source_command_id=command_id,
        decision_epoch=DecisionEpoch.model_validate(followup_epoch_payload),
    )
    probe = _CountingProcessor()
    runtime = SubjectiveRuntime("http://testserver", session_id, event_sink=MemoryAgentEventSink(), processors=[probe])
    runtime.store.load_snapshot(snapshot)
    try:
        ack = CommandResult(
            status=CommandResultStatus.ACCEPTED,
            command_id=command_id,
            session_id=session_id,
            actor_uuid=epoch["actor_uuid"],
            requested_epoch_id=epoch["epoch_id"],
            row_id="position|Move|pos=1,1",
            message="http ack",
            resync_required=False,
        )
        with runtime._state_changed:
            runtime.store.register_pending_command(command_id, ack)
        events, connection_cursors = _start_queue_backed_observation_pump(
            monkeypatch,
            runtime,
            sync_cursor=snapshot["observation_cursor"],
        )
        for frame in [*noise_frames, command_frame, final_noise, followup_frame]:
            events.put(("observation_frame", frame.model_dump(mode="json")))
        result = runtime._wait_for_command_followup(command_id, ack)
    finally:
        runtime.close()

    assert connection_cursors == [snapshot["observation_cursor"]]
    assert result.message == "batched accepted"
    assert runtime.store.world is not None
    assert runtime.store.world.observation_cursor == snapshot["observation_cursor"] + 5
    assert probe.hooks == [
        HookPoint.FRAME_APPLIED,
        HookPoint.ACTION_COMPLETED,
        HookPoint.EPOCH_STARTED,
    ]


def test_runtime_emits_interrupted_hook_for_partial_accepted_action() -> None:
    """Partial authoritative success is distinct from action completion."""
    client, session_id, _hero, _monster, _encounter = create_observation_game()
    snapshot = client.get(
        f"/ai/sessions/{session_id}/observation/snapshot"
    ).json()
    epoch = snapshot["current_epoch"]
    probe = _CountingProcessor()
    runtime = SubjectiveRuntime(
        "http://testserver",
        session_id,
        event_sink=MemoryAgentEventSink(),
        processors=[probe],
    )
    runtime.store.load_snapshot(snapshot)
    frame = ObservationFrame(
        observation_cursor=snapshot["observation_cursor"] + 1,
        frame_type=ObservationFrameType.COMMAND_RESULT,
        source_kind=ObservationSourceKind.CONTROLLER_COMMAND,
        command_result=CommandResult(
            status=CommandResultStatus.ACCEPTED,
            session_id=session_id,
            actor_uuid=epoch["actor_uuid"],
            requested_epoch_id=epoch["epoch_id"],
            row_id="position|Move|pos=1,1",
            action_resolution=ActionResolutionStatus.INTERRUPTED,
            revalidation_required=True,
            revalidation_reason="newly_visible_hostile",
        ),
    )

    try:
        runtime._run_command_result_effects(frame)
    finally:
        runtime.close()

    assert probe.hooks == [HookPoint.ACTION_INTERRUPTED]


def test_runtime_command_followup_requires_correlated_next_actor_epoch(monkeypatch) -> None:
    """An unrelated turn epoch cannot complete a pending command lifecycle."""
    client, session_id, _hero, _monster, _encounter = create_observation_game()
    snapshot = client.get(f"/ai/sessions/{session_id}/observation/snapshot").json()
    first_epoch = snapshot["current_epoch"]
    command_id = str(uuid4())
    next_actor_uuid = str(uuid4())
    next_epoch_payload = dict(first_epoch)
    next_epoch_payload.update({
        "epoch_id": str(uuid4()),
        "epoch_index": first_epoch["epoch_index"] + 1,
        "basis_observation_cursor": snapshot["observation_cursor"] + 1,
        "reason": "turn_start",
        "actor_uuid": next_actor_uuid,
    })
    next_epoch_frame = ObservationFrame(
        observation_cursor=snapshot["observation_cursor"] + 1,
        frame_type=ObservationFrameType.DECISION_EPOCH,
        source_kind=ObservationSourceKind.DECISION_EPOCH,
        source_command_id=None,
        decision_epoch=DecisionEpoch.model_validate(next_epoch_payload),
    )
    command_frame = ObservationFrame(
        observation_cursor=snapshot["observation_cursor"] + 2,
        frame_type=ObservationFrameType.COMMAND_RESULT,
        source_kind=ObservationSourceKind.CONTROLLER_COMMAND,
        source_command_id=command_id,
        command_result=CommandResult(
            status=CommandResultStatus.ACCEPTED,
            command_id=command_id,
            session_id=session_id,
            actor_uuid=first_epoch["actor_uuid"],
            requested_epoch_id=first_epoch["epoch_id"],
            current_epoch_id=None,
            row_id="position|Move|pos=13,10",
            message="Partial movement stopped at current cell.",
            resync_required=False,
        ),
    )
    correlated_epoch_payload = dict(next_epoch_payload)
    correlated_epoch_payload.update({
        "epoch_id": str(uuid4()),
        "epoch_index": next_epoch_payload["epoch_index"] + 1,
        "basis_observation_cursor": snapshot["observation_cursor"] + 2,
    })
    correlated_epoch_frame = ObservationFrame(
        observation_cursor=snapshot["observation_cursor"] + 3,
        frame_type=ObservationFrameType.DECISION_EPOCH,
        source_kind=ObservationSourceKind.DECISION_EPOCH,
        source_command_id=command_id,
        decision_epoch=DecisionEpoch.model_validate(correlated_epoch_payload),
    )
    sink = MemoryAgentEventSink()
    runtime = SubjectiveRuntime("http://testserver", session_id, event_sink=sink, processors=[])
    runtime.store.load_snapshot(snapshot)

    try:
        ack = CommandResult(
            status=CommandResultStatus.ACCEPTED,
            command_id=command_id,
            session_id=session_id,
            actor_uuid=first_epoch["actor_uuid"],
            requested_epoch_id=first_epoch["epoch_id"],
            row_id="position|Move|pos=13,10",
            message="http ack",
            resync_required=False,
        )
        with runtime._state_changed:
            runtime.store.register_pending_command(command_id, ack)
        events, connection_cursors = _start_queue_backed_observation_pump(
            monkeypatch,
            runtime,
            sync_cursor=snapshot["observation_cursor"],
        )
        events.put(("observation_frame", next_epoch_frame.model_dump(mode="json")))
        events.put(("observation_frame", command_frame.model_dump(mode="json")))
        deadline = time.monotonic() + 1.0
        while (
            runtime.store.world is not None
            and runtime.store.world.observation_cursor < command_frame.observation_cursor
            and time.monotonic() < deadline
        ):
            time.sleep(0.001)
        assert not runtime.store.command_control_seen(command_id)
        events.put(("observation_frame", correlated_epoch_frame.model_dump(mode="json")))
        result = runtime._wait_for_command_followup(command_id, ack)
    finally:
        runtime.close()

    assert connection_cursors == [snapshot["observation_cursor"]]
    assert result.message == "Partial movement stopped at current cell."
    assert runtime.store.world is not None
    assert runtime.store.world.current_epoch is not None
    assert runtime.store.world.current_epoch.actor_uuid == next_actor_uuid
    assert runtime.store.world.current_epoch.epoch_id == correlated_epoch_payload["epoch_id"]
    assert runtime.store.world.observation_cursor == snapshot["observation_cursor"] + 3


def test_runtime_emits_command_timing_breakdown_event() -> None:
    """Runtime telemetry separates submit, SSE reduction, hooks, and resync timing."""
    sink = MemoryAgentEventSink()
    runtime = SubjectiveRuntime(
        "http://testserver",
        "session-ai",
        event_sink=sink,
        processors=[],
    )
    probe = CommandTimingProbe(
        command_type="execute",
        command_id="command-1",
        actor_uuid="actor-1",
        epoch_id="epoch-1",
        row_id="entity|Attack|uuid=target-1",
    )
    probe.wait_for_epoch_ms = 0.4
    probe.submit_http_ms = 1.2
    probe.sse_wait_ms = 0.6
    probe.sse_frames = 1
    probe.stream_reduction_ms = 0.8
    probe.stream_frame_parse_ms = 0.5
    probe.stream_store_apply_ms = 0.2
    probe.stream_hook_ms = 0.3
    probe.stream_processor_ms = {"agent_facts": 0.2, "turn_brief": 0.1}
    probe.server_timing = {
        "command_type": "execute",
        "total_ms": 0.9,
        "phases": {"build.current_epoch_ms": 0.1},
    }
    result = CommandResult(
        status=CommandResultStatus.ACCEPTED,
        command_id="command-1",
        session_id="session-ai",
        actor_uuid="actor-1",
        requested_epoch_id="epoch-1",
        row_id="entity|Attack|uuid=target-1",
        message="accepted",
    )

    try:
        runtime._finish_command_timing(probe, result)
    finally:
        runtime.close()

    assert runtime.last_command_timing is not None
    assert runtime.last_command_timing["command_id"] == "command-1"
    assert runtime.last_command_timing["status"] == "accepted"
    assert runtime.last_command_timing["submit_http_ms"] == 1.2
    assert runtime.last_command_timing["stream_reduction_ms"] == 0.8
    assert runtime.last_command_timing["stream_frame_parse_ms"] == 0.5
    assert runtime.last_command_timing["stream_store_apply_ms"] == 0.2
    assert runtime.last_command_timing["stream_hook_ms"] == 0.3
    assert runtime.last_command_timing["automatic_gc_suspended"] is True
    assert runtime.last_command_timing["gc_collections_during_command"] == [0, 0, 0]
    assert runtime.last_command_timing["stream_processor_ms"] == {
        "agent_facts": 0.2,
        "turn_brief": 0.1,
    }
    assert not any(
        field.startswith("history_")
        for field in runtime.last_command_timing
    )
    event = sink.events[-1]
    assert event.event_type == "runtime.command_timing"
    assert event.level == "debug"
    assert event.payload["row_id"] == "entity|Attack|uuid=target-1"
    assert event.payload["stream_reduction_ms"] == 0.8
    assert event.payload["stream_frame_parse_ms"] == 0.5
    assert event.payload["stream_store_apply_ms"] == 0.2
    assert event.payload["stream_hook_ms"] == 0.3
    assert event.payload["server_timing"]["phases"]["build.current_epoch_ms"] == 0.1


def test_automatic_gc_lease_is_nested_and_restores_process_setting() -> None:
    """Multiple runtimes share one suspension and the last close restores GC."""
    originally_enabled = gc.isenabled()
    first = AutomaticGcLease.acquire()
    second = AutomaticGcLease.acquire()
    try:
        assert automatic_gc_suspended()
        first.release()
        assert automatic_gc_suspended()
    finally:
        first.release()
        second.release()

    assert gc.isenabled() is originally_enabled


def test_runtime_can_preserve_embedding_process_gc_policy() -> None:
    """An embedded runtime does not mutate its host process's GC policy."""
    originally_enabled = gc.isenabled()
    runtime = SubjectiveRuntime(
        "http://testserver",
        "embedded-session",
        event_sink=MemoryAgentEventSink(),
        processors=[],
        gc_policy=PRESERVE_AUTOMATIC_GC,
    )
    try:
        assert gc.isenabled() is originally_enabled
    finally:
        runtime.close()

    assert gc.isenabled() is originally_enabled


def test_canceled_engine_action_remains_an_accepted_command_with_detail(monkeypatch) -> None:
    """A legal command canceled by gameplay is distinct from protocol rejection."""
    client, session_id, _hero, _monster, _encounter = create_observation_game()
    snapshot = client.get(f"/ai/sessions/{session_id}/observation/snapshot").json()
    epoch = snapshot["current_epoch"]
    row = _first_affordable_position_row(epoch)
    command_id = str(uuid4())

    async def fake_execute_action_by_index(_request, execution_binding=None):
        assert execution_binding is not None
        return event_server._ActionExecutionResult(
            response=ActionResult(
                success=False,
                message="The spell was interrupted.",
                event_type="spell",
                outcome_code="spell.counterspell.interrupted",
                turn_continues=True,
                encounter_ended=False,
            ),
        )

    monkeypatch.setattr(event_server, "_execute_action_by_index_impl", fake_execute_action_by_index)

    response = client.post(
        f"/ai/sessions/{session_id}/commands/execute",
        json={
            "command_id": command_id,
            "actor_uuid": epoch["actor_uuid"],
            "basis_epoch_id": epoch["epoch_id"],
            "row_id": row["row_id"],
            "prefer_safe": True,
        },
    )
    frames = client.get(
        f"/ai/sessions/{session_id}/observation/frames",
        params={"since": snapshot["observation_cursor"], "limit": 0},
    ).json()["frames"]

    assert response.status_code == 200
    ack = response.json()
    assert ack["status"] == "accepted"
    assert ack["action_resolution"] == ActionResolutionStatus.CANCELED.value
    assert ack["outcome_code"] == "spell.counterspell.interrupted"
    assert ack["message"] == "The spell was interrupted."
    assert ack["payload"]["success"] is False
    command_frame = next(
        frame for frame in frames
        if frame["frame_type"] == "command_result" and frame["source_command_id"] == command_id
    )
    streamed_result = command_frame["command_result"]
    assert streamed_result["status"] == "accepted"
    assert streamed_result["action_resolution"] == "canceled"
    assert streamed_result["outcome_code"] == "spell.counterspell.interrupted"
    assert streamed_result["payload"]["success"] is False
    assert "event_data" not in streamed_result["payload"]
    followup_epoch = next(
        frame for frame in frames
        if frame["frame_type"] == "decision_epoch" and frame["source_command_id"] == command_id
    )
    assert followup_epoch["decision_epoch"]["reason"] == "action_canceled"


def test_action_adapter_reports_missing_engine_event_as_failure(monkeypatch) -> None:
    """An action that produces no engine event must never be reported as executed."""
    client, session_id, hero, _monster, _encounter = create_observation_game()
    snapshot = client.get(f"/ai/sessions/{session_id}/observation/snapshot").json()
    row = _first_affordable_position_row(snapshot["current_epoch"])

    monkeypatch.setattr(event_server, "execute_available_action", lambda *_args, **_kwargs: None)

    response = client.post(
        "/action/execute",
        json={
            "session_id": session_id,
            "entity_uuid": str(hero.uuid),
            "template_name": row["template_name"],
            "target_index": row["targets"][0]["index"],
            "return_available_actions": False,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is False
    assert payload["message"] == f"{row['template_name']} could not be executed"
    assert payload["message"] != f"{row['template_name']} executed"


def test_snapshot_current_epoch_is_bootstrap_only_not_frame_decoration() -> None:
    """Frame polling returns historical envelopes without route-level epoch injection."""
    client, session_id, hero, _monster, _encounter = create_observation_game()
    snapshot = client.get(f"/ai/sessions/{session_id}/observation/snapshot").json()
    command_id = str(uuid4())

    end_response = client.post(
        f"/ai/sessions/{session_id}/commands/end-turn",
        json={
            "command_id": command_id,
            "actor_uuid": str(hero.uuid),
            "basis_epoch_id": snapshot["current_epoch"]["epoch_id"],
        },
    )
    frames = client.get(
        f"/ai/sessions/{session_id}/observation/frames",
        params={"since": snapshot["observation_cursor"], "limit": 0},
    ).json()["frames"]

    assert end_response.status_code == 200
    assert end_response.json()["status"] == "accepted"
    assert end_response.json()["row_id"] == END_TURN_ROW_ID
    assert end_response.json()["payload"]["server_timing"]["command_type"] == "end_turn"
    assert "end_turn.advance_encounter_ms" in end_response.json()["payload"]["server_timing"]["phases"]
    assert any(frame["frame_type"] == "command_result" for frame in frames)
    control_frames = [
        frame
        for frame in frames
        if frame["frame_type"] == "decision_epoch"
        and frame["source_command_id"] == command_id
    ]
    assert len(control_frames) == 1
    assert control_frames[0]["decision_epoch"] is not None
    assert control_frames[0]["decision_epoch"]["reason"] == "turn_start"
    assert all(
        frame["decision_epoch"] is None
        for frame in frames
        if frame["frame_type"] != "decision_epoch"
    )


def test_command_result_frames_carry_protocol_outcome_not_objective_gameplay_payloads() -> None:
    """Gameplay facts arrive as subjective events, never raw action or advancement payloads."""
    client, session_id, hero, _monster, _encounter = create_observation_game()
    snapshot = client.get(f"/ai/sessions/{session_id}/observation/snapshot").json()
    epoch = snapshot["current_epoch"]
    row = _first_affordable_position_row(epoch)
    execute_command_id = str(uuid4())

    execute_response = client.post(
        f"/ai/sessions/{session_id}/commands/execute",
        json={
            "command_id": execute_command_id,
            "actor_uuid": epoch["actor_uuid"],
            "basis_epoch_id": epoch["epoch_id"],
            "row_id": row["row_id"],
            "prefer_safe": True,
        },
    )
    execute_frames = client.get(
        f"/ai/sessions/{session_id}/observation/frames",
        params={"since": snapshot["observation_cursor"], "limit": 0},
    ).json()["frames"]
    execute_frame = next(
        frame
        for frame in execute_frames
        if frame["frame_type"] == "command_result"
        and frame["source_command_id"] == execute_command_id
    )
    execute_payload = execute_frame["command_result"]["payload"]

    assert execute_response.status_code == 200
    assert set(execute_payload) <= {
        "success",
        "turn_continues",
        "encounter_ended",
        "server_timing",
        "action_server_timing",
    }

    followup_epoch = next(
        frame["decision_epoch"]
        for frame in execute_frames
        if frame["frame_type"] == "decision_epoch"
        and frame["source_command_id"] == execute_command_id
        and frame["decision_epoch"] is not None
    )
    end_command_id = str(uuid4())
    end_response = client.post(
        f"/ai/sessions/{session_id}/commands/end-turn",
        json={
            "command_id": end_command_id,
            "actor_uuid": str(hero.uuid),
            "basis_epoch_id": followup_epoch["epoch_id"],
        },
    )
    end_frames = client.get(
        f"/ai/sessions/{session_id}/observation/frames",
        params={"since": execute_frames[-1]["observation_cursor"], "limit": 0},
    ).json()["frames"]
    end_frame = next(
        frame
        for frame in end_frames
        if frame["frame_type"] == "command_result"
        and frame["source_command_id"] == end_command_id
    )
    end_payload = end_frame["command_result"]["payload"]

    assert end_response.status_code == 200
    assert set(end_payload) <= {"status", "encounter_ended", "server_timing"}
    assert "ai_actions" not in json.dumps(end_frame)
