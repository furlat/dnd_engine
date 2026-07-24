"""Focused lifecycle checks for the standalone embedded AI service."""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
import subprocess
import sys
from threading import Event, Lock

import pytest

from ai.in_process_agent_service import (
    EMBEDDED_CONTROL_REQUEST_TIMEOUT_SECONDS,
    EmbeddedSubjectiveAgentService,
    create_embedded_subjective_agent,
)
from ai.subjective.runtime_gc import PRESERVE_AUTOMATIC_GC
from server.agent_runtime.service import AgentLaunchRequest
from server.agent_runtime.service_manager import (
    AgentServiceStartError,
    AgentServiceStopError,
    ManagedAgentServiceManager,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


class _BlockingAgent:
    """Thread-safe fake policy loop with explicit readiness and shutdown."""

    def __init__(
        self,
        request: AgentLaunchRequest,
        manager: ManagedAgentServiceManager,
    ) -> None:
        self.request = request
        self.manager = manager
        self.started = Event()
        self.stop_requested = Event()
        self.closed = Event()

    def run_forever(self) -> None:
        assert self.request.readiness_token is not None
        assert self.manager.acknowledge_ready(
            self.request.session_id,
            self.request.readiness_token,
        )
        self.started.set()
        self.stop_requested.wait()

    def request_stop(self) -> None:
        self.stop_requested.set()

    def close(self, timeout_seconds: float = 4.0) -> None:
        del timeout_seconds
        self.closed.set()


class _RecordingFactory:
    """Create one independent fake agent per launch request."""

    def __init__(
        self,
        manager: ManagedAgentServiceManager,
        *,
        failing_session_id: str | None = None,
    ) -> None:
        self.manager = manager
        self.failing_session_id = failing_session_id
        self._lock = Lock()
        self.agents: dict[str, _BlockingAgent] = {}

    def __call__(self, request: AgentLaunchRequest) -> _BlockingAgent:
        if request.session_id == self.failing_session_id:
            raise RuntimeError(f"factory refused {request.session_id}")
        agent = _BlockingAgent(request, self.manager)
        with self._lock:
            self.agents[request.session_id] = agent
        return agent


class _CloseFailingAgent(_BlockingAgent):
    """Agent whose policy loop stops but whose owned cleanup reports failure."""

    def close(self, timeout_seconds: float = 4.0) -> None:
        super().close(timeout_seconds)
        raise RuntimeError("telemetry worker survived")


def _request(session_id: str) -> AgentLaunchRequest:
    return AgentLaunchRequest(
        session_id=session_id,
        base_url="http://127.0.0.1:8123",
        spawned_at=123.0,
    )


def test_embedded_service_starts_independent_agents_and_stops_exact_session() -> None:
    """Two local AI sides share code, never runtime state or lifecycle."""
    manager = ManagedAgentServiceManager(
        startup_timeout_seconds=1.0,
        readiness_poll_seconds=0.001,
    )
    factory = _RecordingFactory(manager)
    manager.register_service(EmbeddedSubjectiveAgentService(factory))

    async def exercise() -> None:
        handles = await manager.start_agents((
            _request("session-a"),
            _request("session-b"),
        ))
        assert len(handles) == 2
        assert manager.execution_mode == "embedded_thread"
        assert manager.running_session_ids() == ["session-a", "session-b"]
        assert all(row["ready"] for row in manager.session_statuses())
        assert all(row["process_id"] is None for row in manager.session_statuses())
        assert factory.agents["session-a"] is not factory.agents["session-b"]

        await manager.stop_session("session-a")
        assert factory.agents["session-a"].closed.wait(timeout=1.0)
        assert manager.is_running("session-a") is False
        assert manager.is_running("session-b") is True
        assert factory.agents["session-b"].stop_requested.is_set() is False

        await manager.stop_all()
        assert factory.agents["session-b"].closed.wait(timeout=1.0)

    asyncio.run(exercise())
    assert manager.session_statuses() == []


def test_embedded_batch_failure_rolls_back_every_started_thread() -> None:
    """A failed second policy cannot leave the first session running."""
    manager = ManagedAgentServiceManager(
        startup_timeout_seconds=1.0,
        readiness_poll_seconds=0.001,
    )
    factory = _RecordingFactory(manager, failing_session_id="session-b")
    manager.register_service(EmbeddedSubjectiveAgentService(factory))

    with pytest.raises(AgentServiceStartError, match="factory refused session-b"):
        asyncio.run(manager.start_agents((
            _request("session-a"),
            _request("session-b"),
        )))

    assert factory.agents["session-a"].stop_requested.is_set()
    assert factory.agents["session-a"].closed.wait(timeout=1.0)
    assert manager.session_statuses() == []


def test_embedded_cleanup_failure_is_retained_by_manager() -> None:
    """The manager cannot forget a handle whose owned child cleanup failed."""
    manager = ManagedAgentServiceManager(
        startup_timeout_seconds=1.0,
        readiness_poll_seconds=0.001,
    )
    agents: list[_CloseFailingAgent] = []

    def factory(request: AgentLaunchRequest) -> _CloseFailingAgent:
        agent = _CloseFailingAgent(request, manager)
        agents.append(agent)
        return agent

    manager.register_service(EmbeddedSubjectiveAgentService(factory))

    async def exercise() -> None:
        await manager.start_agents((_request("session-a"),))
        with pytest.raises(
            AgentServiceStopError,
            match="telemetry worker survived",
        ):
            await manager.stop_session("session-a")

    asyncio.run(exercise())

    assert agents[0].closed.is_set()
    assert len(manager.session_statuses()) == 1
    assert manager.session_statuses()[0]["running"] is False
    assert "telemetry worker survived" in str(
        manager.session_statuses()[0]["failure"]
    )


def test_embedded_factory_preserves_server_gc_and_forwards_canonical_transport(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The adapter changes placement only, not the agent's transport contract."""
    captured: dict[str, object] = {}
    sentinel = object()

    def fake_external_agent(
        base_url: str,
        session_id: str,
        **options: object,
    ) -> object:
        captured.update({
            "base_url": base_url,
            "session_id": session_id,
            **options,
        })
        return sentinel

    monkeypatch.setattr(
        "ai.in_process_agent_service.EmbeddedExternalAgent",
        fake_external_agent,
    )
    request = AgentLaunchRequest(
        session_id="session-a",
        base_url="http://127.0.0.1:8123/",
        spawned_at=123.0,
        unix_socket_path="/tmp/game.sock",
        readiness_token="ready-token",
    )

    assert create_embedded_subjective_agent(request) is sentinel
    assert captured == {
        "base_url": "http://127.0.0.1:8123",
        "session_id": "session-a",
        "unix_socket_path": "/tmp/game.sock",
        "readiness_token": "ready-token",
        "gc_policy": PRESERVE_AUTOMATIC_GC,
        "control_request_timeout": EMBEDDED_CONTROL_REQUEST_TIMEOUT_SECONDS,
    }


def test_local_server_composition_registers_embedded_service_without_popen() -> None:
    """Importing the standalone composition preloads AI but spawns no child."""
    marker = "__DND_EMBEDDED_AGENT_SERVICE__="
    script = (
        "import json, subprocess\n"
        "def reject_popen(*args, **kwargs):\n"
        "    raise AssertionError('standalone composition spawned a subprocess')\n"
        "subprocess.Popen = reject_popen\n"
        "import ai.local_game_server\n"
        "from server.event_server import agent_service_manager\n"
            f"print({marker!r} + json.dumps({{"
            "'service_id': agent_service_manager.service_id, "
            "'execution_mode': agent_service_manager.execution_mode"
            "}, sort_keys=True))\n"
        )
    environment = os.environ.copy()
    environment.pop("DND_EXTERNAL_AGENT_MODULE", None)
    completed = subprocess.run(
        [sys.executable, "-c", script],
        cwd=REPOSITORY_ROOT,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
        env=environment,
    )

    assert completed.returncode == 0, (
        "Embedded AI composition failed before service registration:\n"
        f"stdout:\n{completed.stdout}\n"
        f"stderr:\n{completed.stderr}"
    )
    marker_lines = [
        line for line in completed.stdout.splitlines() if line.startswith(marker)
    ]
    assert len(marker_lines) == 1
    assert json.loads(marker_lines[0][len(marker):]) == {
        "service_id": "ai.embedded-subjective-policy",
        "execution_mode": "embedded_thread",
    }
