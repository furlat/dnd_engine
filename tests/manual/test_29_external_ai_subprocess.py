"""Focused integration checks for the external shared-policy subprocess."""

import asyncio
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
from typing import Any

import pytest

from ai.knowledge import derive_agent_facts
from server.agent_protocol.observation_replay import materialize_snapshot
from ai.policy import PolicyGoal, PolicyHost
from dnd.entity import Entity
from server import event_server
from server.agent_runtime.service import (
    AgentExecutionMode,
    AgentHandleStatus,
    AgentLaunchRequest,
    ManagedAgentHandle,
)
from server.agent_runtime.service_manager import (
    AgentServiceStartError,
    AgentServiceUnavailableError,
    ManagedAgentServiceManager,
)
from server.agent_runtime.subprocess_service import (
    AgentProcessSpec,
    SubprocessAgentHandle,
    SubprocessAgentService,
)
from server.arena_mode import ArenaApiClient, reset_standard_arena_runtime
from server.session import PlayerType


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def _async_append(rows: list[str], value: str):
    """Return an async no-argument recorder for lifecycle monkeypatches."""
    async def append() -> None:
        rows.append(value)

    return append


class _FakeProcess:
    """Small Popen-compatible lifecycle probe."""

    def __init__(self) -> None:
        self.pid = 43210
        self.returncode: int | None = None
        self.terminate_calls = 0
        self.kill_calls = 0
        self.wait_timeouts: list[float] = []

    def poll(self) -> int | None:
        return self.returncode

    def terminate(self) -> None:
        self.terminate_calls += 1
        self.returncode = 0

    def kill(self) -> None:
        self.kill_calls += 1
        self.returncode = -9

    def wait(self, timeout: float) -> int:
        self.wait_timeouts.append(timeout)
        assert self.returncode is not None
        return self.returncode


class _UnstoppableProcess(_FakeProcess):
    """Process probe whose operating-system termination request fails."""

    def terminate(self) -> None:
        self.terminate_calls += 1
        raise OSError("terminate refused")

    def wait(self, timeout: float) -> int:
        self.wait_timeouts.append(timeout)
        if self.returncode is None:
            raise subprocess.TimeoutExpired("test-agent", timeout)
        return self.returncode


class _SequencedPollProcess(_FakeProcess):
    """Process probe that exposes accidental repeated status polling."""

    def __init__(self, poll_results: list[int | None]) -> None:
        super().__init__()
        self._poll_results = poll_results
        self.poll_calls = 0

    def poll(self) -> int | None:
        result = self._poll_results[min(
            self.poll_calls,
            len(self._poll_results) - 1,
        )]
        self.poll_calls += 1
        return result


class _LifecycleProbeHandle:
    """Managed handle whose invalid metadata must not defeat cleanup."""

    def __init__(
        self,
        *,
        public_session_id: str,
        status_session_id: str,
        execution_mode: AgentExecutionMode,
        running: bool,
    ) -> None:
        self._public_session_id = public_session_id
        self._status_session_id = status_session_id
        self._execution_mode = execution_mode
        self._running = running
        self.request_stop_calls = 0
        self.wait_stopped_calls = 0

    @property
    def session_id(self) -> str:
        return self._public_session_id

    def status(self) -> AgentHandleStatus:
        return AgentHandleStatus(
            session_id=self._status_session_id,
            execution_mode=self._execution_mode,
            running=self._running,
        )

    def request_stop(self) -> None:
        self.request_stop_calls += 1

    async def wait_stopped(self, timeout_seconds: float) -> None:
        assert timeout_seconds > 0
        self.wait_stopped_calls += 1
        self._running = False


class _ReturningService:
    """Service probe returning one preconstructed lifecycle handle."""

    service_id = "tests.returning-service"
    execution_mode = AgentExecutionMode.ISOLATED_PROCESS

    def __init__(self, handle: _LifecycleProbeHandle) -> None:
        self._handle = handle

    def preflight(self, required_agents: int) -> None:
        assert required_agents == 1

    def start(self, request: AgentLaunchRequest) -> ManagedAgentHandle:
        del request
        return self._handle


class _RecordingLauncher:
    """Dependency-neutral launcher used to exercise the server supervisor."""

    service_id = "tests.recording-agent"

    def __init__(self) -> None:
        self.preflight_counts: list[int] = []
        self.requests: list[AgentLaunchRequest] = []

    def preflight(self, required_agents: int) -> None:
        self.preflight_counts.append(required_agents)

    def build_process_spec(self, request: AgentLaunchRequest) -> AgentProcessSpec:
        self.requests.append(request)
        argv = (
            "test-agent",
            "--base-url",
            request.base_url.rstrip("/"),
            "--session-id",
            str(request.session_id),
            "--spawned-at",
            str(request.spawned_at),
        )
        if request.unix_socket_path is not None:
            argv = (*argv, "--unix-socket", request.unix_socket_path)
        return AgentProcessSpec(
            argv=argv,
            cwd=REPOSITORY_ROOT,
        )


@pytest.fixture(autouse=True)
def isolate_global_agent_launcher() -> Any:
    """Prevent explicit launcher registration from leaking between route tests."""
    service_id = event_server.agent_service_manager.service_id
    if service_id is not None:
        event_server.agent_service_manager.unregister_service(service_id)
    yield
    event_server.agent_service_manager.stop_all_blocking()
    service_id = event_server.agent_service_manager.service_id
    if service_id is not None:
        event_server.agent_service_manager.unregister_service(service_id)


def _move_target_index(actions_payload: dict[str, object], position: tuple[int, int]) -> int:
    """Return the public Move target index for one grid position."""
    for action in actions_payload.get("position_actions", []):  # type: ignore[union-attr]
        if not isinstance(action, dict) or action.get("template_name") != "Move":
            continue
        for target in action.get("valid_targets", []):
            if isinstance(target, dict) and tuple(target.get("position") or ()) == position:
                return int(target["index"])
    raise AssertionError(f"Move target {position} was not present")


def test_start_human_creates_ai_session_and_spawns_once(monkeypatch) -> None:
    """The human arena assigns all monsters to one shared-policy subprocess."""
    reset_standard_arena_runtime()
    event_server.agent_service_manager.register_service(
        SubprocessAgentService(_RecordingLauncher())
    )
    starts: list[tuple[str, str]] = []

    async def fake_start_agents(
        requests: tuple[AgentLaunchRequest, ...],
    ) -> tuple[object, ...]:
        starts.extend(
            (str(request.session_id), request.base_url)
            for request in requests
        )
        return ()

    monkeypatch.setattr(
        event_server.agent_service_manager,
        "start_agents",
        fake_start_agents,
    )

    client = ArenaApiClient()
    response = client.post(
        "/simulation/start-human",
        params={"character_class": "fighter"},
    )
    payload = response.json()
    game_status = client.get("/game/status").json()
    monsters = [entity for entity in Entity.get_all_entities() if entity.faction == "monsters"]
    encounter = event_server.sim.encounter
    assert encounter is not None
    controller_types = {
        controller.controller_type
        for monster in monsters
        for controller in [encounter.get_controller_for(monster.uuid)]
        if controller is not None
    }
    ai_sessions = [session for session in game_status["sessions"] if session["player_type"] == "ai"]

    assert response.status_code == 200
    assert payload["status"] == "waiting_for_human"
    assert payload["entity_uuid"] == payload["hero_uuid"]
    assert payload["ai_session_id"] == starts[0][0]
    assert starts == [(payload["ai_session_id"], "http://testserver")]
    assert controller_types == {"external_ai"}
    assert len(ai_sessions) == 1
    assert ai_sessions[0]["name"] == "AI Monsters"
    assert len(ai_sessions[0]["controlled_entities"]) == 3


def test_managed_agent_attachment_ignores_untrusted_host_header(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A client cannot redirect the server-owned AI transport endpoint."""
    reset_standard_arena_runtime()
    event_server.agent_service_manager.register_service(
        SubprocessAgentService(_RecordingLauncher())
    )
    requests_seen: list[AgentLaunchRequest] = []

    async def capture_batch(
        requests: tuple[AgentLaunchRequest, ...],
    ) -> tuple[object, ...]:
        requests_seen.extend(requests)
        return ()

    monkeypatch.setattr(
        event_server.agent_service_manager,
        "start_agents",
        capture_batch,
    )
    client = ArenaApiClient()

    response = client.post(
        "/simulation/start-human",
        params={"character_class": "fighter"},
        headers={"host": "attacker.invalid:9443"},
    )

    assert response.status_code == 200
    assert len(requests_seen) == 1
    assert requests_seen[0].base_url == "http://testserver"


def test_pre_contact_side_move_does_not_create_monster_target_pressure(monkeypatch) -> None:
    """The streamed epoch and shared policy remain strictly session-subjective."""
    reset_standard_arena_runtime()
    event_server.agent_service_manager.register_service(
        SubprocessAgentService(_RecordingLauncher())
    )
    monkeypatch.setattr(
        event_server.agent_service_manager,
        "start_agents",
        _empty_agent_start,
    )

    client = ArenaApiClient()
    start = client.post("/simulation/start-human", params={"character_class": "sorcerer"})
    assert start.status_code == 200
    start_payload = start.json()
    hero_uuid = start_payload["hero_uuid"]
    monster_session_id = start_payload["ai_session_id"]
    bootstrap = client.get(f"/ai/sessions/{monster_session_id}/observation/snapshot")
    assert bootstrap.status_code == 200
    bootstrap_cursor = bootstrap.json()["observation_cursor"]
    bootstrap_text = json.dumps(bootstrap.json())
    assert str(hero_uuid) not in bootstrap_text
    assert "Hero" not in bootstrap_text

    session = client.post("/session/create", json={"player_type": "human", "name": "Arena Player"})
    assert session.status_code == 200
    hero_session_id = session.json()["session_id"]
    join = client.post(
        "/game/join",
        json={"session_id": hero_session_id, "entity_uuids": [hero_uuid]},
    )
    assert join.status_code == 200

    hero_actions = client.get(
        f"/entity/{hero_uuid}/available-actions",
        params={"session_id": hero_session_id},
    )
    assert hero_actions.status_code == 200
    side_move_index = _move_target_index(hero_actions.json(), (2, 8))
    move = client.post(
        "/action/execute",
        json={
            "session_id": hero_session_id,
            "entity_uuid": hero_uuid,
            "template_name": "Move",
            "target_index": side_move_index,
        },
    )
    assert move.status_code == 200
    end_turn = client.post(
        "/action/end-turn",
        json={"session_id": hero_session_id, "entity_uuid": hero_uuid},
    )
    assert end_turn.status_code == 200

    frames = client.get(
        f"/ai/sessions/{monster_session_id}/observation/frames",
        params={"since": bootstrap_cursor, "limit": 200},
    )
    assert frames.status_code == 200
    stream_text = json.dumps(frames.json())
    assert str(hero_uuid) not in stream_text
    assert "Hero" not in stream_text

    snapshot_response = client.get(f"/ai/sessions/{monster_session_id}/observation/snapshot")
    assert snapshot_response.status_code == 200
    snapshot_text = json.dumps(snapshot_response.json())
    assert str(hero_uuid) not in snapshot_text
    assert "Hero" not in snapshot_text
    world = materialize_snapshot(snapshot_response.json())
    facts = derive_agent_facts(world).facts
    decision = PolicyHost().decide(world, facts=facts)

    assert facts.contacts.visible_hostile_uuids == tuple()
    assert facts.contacts.remembered_hostile_uuids == tuple()
    assert decision.selected.goal not in {
        PolicyGoal.DIRECT_PRESSURE,
        PolicyGoal.HOSTILE_CONTROL,
    }


def test_start_codex_monsters_mode_spawns_shared_policy_hero(monkeypatch) -> None:
    """Codex-monsters mode assigns the hero to the same external policy stack."""
    reset_standard_arena_runtime()
    event_server.agent_service_manager.register_service(
        SubprocessAgentService(_RecordingLauncher())
    )
    starts: list[tuple[str, str]] = []

    async def fake_start_agents(
        requests: tuple[AgentLaunchRequest, ...],
    ) -> tuple[object, ...]:
        starts.extend(
            (str(request.session_id), request.base_url)
            for request in requests
        )
        return ()

    monkeypatch.setattr(
        event_server.agent_service_manager,
        "start_agents",
        fake_start_agents,
    )

    client = ArenaApiClient()
    response = client.post("/simulation/start-codex-monsters", params={"character_class": "fighter"})
    payload = response.json()
    game_status = client.get("/game/status").json()
    encounter = event_server.sim.encounter
    assert encounter is not None
    hero = next(entity for entity in Entity.get_all_entities() if entity.faction == "heroes")
    monsters = [entity for entity in Entity.get_all_entities() if entity.faction == "monsters"]
    hero_controller = encounter.get_controller_for(hero.uuid)
    monster_controller_types = {
        controller.controller_type
        for monster in monsters
        for controller in [encounter.get_controller_for(monster.uuid)]
        if controller is not None
    }
    ai_sessions = [session for session in game_status["sessions"] if session["player_type"] == "ai"]

    assert response.status_code == 200
    assert payload["mode"] == "codex_monsters"
    assert starts == [(payload["hero_ai_session_id"], "http://testserver")]
    assert hero_controller is not None
    assert hero_controller.controller_type == "external_ai"
    assert monster_controller_types == {"codex"}
    assert len(payload["monsters"]) == 3
    assert len(ai_sessions) == 1
    assert ai_sessions[0]["name"] == "AI Hero"
    assert ai_sessions[0]["controlled_entities"] == [str(hero.uuid)]


def test_start_aoe_test_launches_its_registered_ai_session(monkeypatch) -> None:
    """The AoE arena cannot create an assigned but unserved AI side."""
    reset_standard_arena_runtime()
    event_server.agent_service_manager.register_service(
        SubprocessAgentService(_RecordingLauncher())
    )
    requests_seen: list[AgentLaunchRequest] = []

    async def capture_batch(
        requests: tuple[AgentLaunchRequest, ...],
    ) -> tuple[object, ...]:
        requests_seen.extend(requests)
        return ()

    monkeypatch.setattr(
        event_server.agent_service_manager,
        "start_agents",
        capture_batch,
    )
    client = ArenaApiClient()

    response = client.post("/simulation/start-aoe-test")
    ai_sessions = [
        session
        for session in event_server.sim.get_session_manager().sessions.values()
        if session.player_type.value == "ai"
    ]

    assert response.status_code == 200
    assert len(ai_sessions) == 1
    assert [request.session_id for request in requests_seen] == [
        str(ai_sessions[0].session_id)
    ]
    assert requests_seen[0].base_url == "http://testserver"


def test_ai_service_diagnostics_and_reset_cleanup(monkeypatch) -> None:
    """Service diagnostics remain exposed and reset stops managed runtimes."""
    reset_standard_arena_runtime()
    stop_calls: list[str] = []

    async def capture_stop_all() -> None:
        envelope = await observation_subscription.get()
        stop_calls.append(str(envelope["data"]["reason"]))

    monkeypatch.setattr(
        event_server.agent_service_manager,
        "stop_all",
        capture_stop_all,
    )

    client = ArenaApiClient()
    status_response = client.get("/ai/service")
    observation_subscription = event_server.observation_wakeup_stream.subscribe(
        "managed-session"
    )
    monkeypatch.setattr(
        event_server.agent_service_manager,
        "running_session_ids",
        lambda: ["managed-session"],
    )
    reset_response = client.post("/simulation/reset")

    assert status_response.status_code == 200
    assert status_response.json() == {
        "service_registered": False,
        "service_id": None,
        "execution_mode": None,
        "sessions": [],
        "running_session_ids": [],
    }
    assert reset_response.status_code == 200
    assert reset_response.json()["status"] == "reset"
    assert stop_calls == ["managed_agent_stopping"]


def test_deleting_ai_session_stops_its_exact_owned_process(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Session authority cannot disappear while its child remains alive."""
    reset_standard_arena_runtime()
    manager = event_server.sim.get_session_manager()
    session = manager.create_session(PlayerType.AI, "Owned AI")
    stopped_sessions: list[str] = []

    async def capture_stop_session(session_id: str) -> None:
        stopped_sessions.append(str(session_id))

    monkeypatch.setattr(
        event_server.agent_service_manager,
        "stop_session",
        capture_stop_session,
    )

    result = asyncio.run(
        event_server.delete_session(str(session.session_id))
    )

    assert result == {
        "status": "deleted",
        "session_id": str(session.session_id),
    }
    assert stopped_sessions == [str(session.session_id)]
    assert manager.get_session(session.session_id) is None


def test_server_signal_stops_owned_agents_before_uvicorn_shutdown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A server signal releases live agent SSE clients before Uvicorn drains."""
    stop_calls: list[str] = []
    monkeypatch.setattr(
        event_server.agent_service_manager,
        "request_stop_all",
        lambda: stop_calls.append("stop"),
    )
    config = event_server.uvicorn.Config(app=event_server.app)
    server = event_server._ManagedAgentUvicornServer(config)

    server.handle_exit(signal.SIGINT, None)

    assert stop_calls == ["stop"]
    assert server.should_exit is True


def test_exceptional_app_lifespan_stops_agents_before_streams(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Exceptional ASGI teardown retains the same ownership cleanup order."""
    calls: list[str] = []
    monkeypatch.setattr(
        event_server.event_stream,
        "start",
        lambda: calls.append("event_start"),
    )
    monkeypatch.setattr(
        event_server.event_stream,
        "stop",
        lambda: calls.append("event_stop"),
    )
    monkeypatch.setattr(
        event_server.canonical_subjective_replication_runtime,
        "ensure_attached",
        lambda: calls.append("replication_start"),
    )
    monkeypatch.setattr(
        event_server.canonical_subjective_replication_runtime,
        "stop",
        lambda: calls.append("replication_stop"),
    )
    monkeypatch.setattr(
        event_server.game_summary_store,
        "ensure_attached",
        lambda: calls.append("summary_start"),
    )
    monkeypatch.setattr(
        event_server.agent_service_manager,
        "stop_all",
        _async_append(calls, "agents_stop"),
    )

    async def fail_inside_lifespan() -> None:
        async with event_server.lifespan(event_server.app):
            raise RuntimeError("lifespan probe")

    with pytest.raises(RuntimeError, match="lifespan probe"):
        asyncio.run(fail_inside_lifespan())

    assert calls == [
        "event_start",
        "replication_start",
        "summary_start",
        "agents_stop",
        "replication_stop",
        "event_stop",
    ]


def test_run_server_treats_keyboard_interrupt_as_normal_shutdown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The explicit Uvicorn composition keeps Ctrl-C free of a traceback."""
    monkeypatch.setattr(
        event_server._ManagedAgentUvicornServer,
        "run",
        lambda _server: (_ for _ in ()).throw(KeyboardInterrupt),
    )

    event_server.run_server(host="127.0.0.1", port=8765)


def _launch_request(session_id: str) -> AgentLaunchRequest:
    """Build one deterministic launch request."""
    return AgentLaunchRequest(
        session_id=session_id,
        base_url="http://testserver/runtime/",
        spawned_at=1234.5,
    )


async def _empty_agent_start(
    _requests: tuple[AgentLaunchRequest, ...],
) -> tuple[object, ...]:
    """Bypass real process creation in in-process route checks."""
    return ()


def _start_with_readiness_ack(
    manager: ManagedAgentServiceManager,
    launcher: _RecordingLauncher,
    requests: tuple[AgentLaunchRequest, ...],
) -> tuple[ManagedAgentHandle, ...]:
    """Start fake processes while acknowledging every prepared request."""

    async def start() -> tuple[ManagedAgentHandle, ...]:
        task = asyncio.create_task(manager.start_agents(requests))
        while len(launcher.requests) < len(requests):
            if task.done():
                return await task
            await asyncio.sleep(0)
        for prepared in launcher.requests[-len(requests):]:
            assert prepared.readiness_token is not None
            assert manager.acknowledge_ready(
                prepared.session_id,
                prepared.readiness_token,
            )
        return await task

    return asyncio.run(start())


@pytest.mark.parametrize(
    (
        "public_session_id",
        "status_session_id",
        "execution_mode",
        "running",
    ),
    (
        (
            "wrong-public-session",
            "session-invalid",
            AgentExecutionMode.ISOLATED_PROCESS,
            True,
        ),
        (
            "session-invalid",
            "wrong-status-session",
            AgentExecutionMode.ISOLATED_PROCESS,
            True,
        ),
        (
            "session-invalid",
            "session-invalid",
            AgentExecutionMode.EMBEDDED_THREAD,
            True,
        ),
        (
            "session-invalid",
            "session-invalid",
            AgentExecutionMode.ISOLATED_PROCESS,
            False,
        ),
    ),
)
def test_invalid_returned_handle_is_stopped_and_joined_before_rollback(
    public_session_id: str,
    status_session_id: str,
    execution_mode: AgentExecutionMode,
    running: bool,
) -> None:
    """Service metadata failure cannot orphan the exact returned handle."""
    handle = _LifecycleProbeHandle(
        public_session_id=public_session_id,
        status_session_id=status_session_id,
        execution_mode=execution_mode,
        running=running,
    )
    manager = ManagedAgentServiceManager()
    manager.register_service(_ReturningService(handle))

    with pytest.raises(AgentServiceStartError):
        asyncio.run(
            manager.start_agents((_launch_request("session-invalid"),))
        )

    assert handle.request_stop_calls == 1
    assert handle.wait_stopped_calls == 1
    assert manager.session_statuses() == []


def test_subprocess_status_uses_one_coherent_poll_snapshot() -> None:
    """Running and return-code diagnostics come from one process poll."""
    process = _SequencedPollProcess([None, 17])
    handle = SubprocessAgentHandle("session-status", process)  # type: ignore[arg-type]

    status = handle.status()

    assert process.poll_calls == 1
    assert status.running is True
    assert status.return_code is None


def test_subprocess_stop_escalation_shares_one_total_deadline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The post-kill wait receives only the first wait's remaining budget."""
    process = _UnstoppableProcess()
    handle = SubprocessAgentHandle("session-deadline", process)  # type: ignore[arg-type]
    monotonic_values = iter((10.0, 10.0, 10.75))
    monkeypatch.setattr(
        "server.agent_runtime.subprocess_service.monotonic",
        lambda: next(monotonic_values),
    )

    handle.request_stop()
    asyncio.run(handle.wait_stopped(1.0))

    assert process.terminate_calls == 1
    assert process.kill_calls == 1
    assert process.wait_timeouts == pytest.approx([1.0, 0.25])
    assert handle.status().failure is None


def test_managed_agent_start_waits_for_exact_readiness_ack(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A live process is not a usable registered service until its exact ack."""
    manager = ManagedAgentServiceManager(
        startup_timeout_seconds=0.5,
        readiness_poll_seconds=0.001,
    )
    launcher = _RecordingLauncher()
    manager.register_service(SubprocessAgentService(launcher))
    process = _FakeProcess()
    monkeypatch.setattr(
        "server.agent_runtime.subprocess_service.subprocess.Popen",
        lambda *_args, **_kwargs: process,
    )

    async def launch_and_ack() -> tuple[ManagedAgentHandle, ...]:
        start_task = asyncio.create_task(
            manager.start_agents((_launch_request("session-ready"),))
        )
        while not launcher.requests:
            await asyncio.sleep(0)
        prepared = launcher.requests[0]
        assert prepared.readiness_token is not None
        assert manager.is_ready("session-ready") is False
        assert manager.acknowledge_ready(
            "session-ready",
            "wrong-token",
        ) is False
        assert manager.acknowledge_ready(
            "session-ready",
            prepared.readiness_token,
        ) is True
        return await start_task

    started = asyncio.run(launch_and_ack())

    assert len(started) == 1
    assert started[0].status().process_id == process.pid
    assert manager.is_ready("session-ready") is True
    assert manager.session_statuses() == [
        {
            "session_id": "session-ready",
            "execution_mode": "isolated_process",
            "running": True,
            "ready": True,
            "process_id": process.pid,
            "return_code": None,
            "failure": None,
        }
    ]


def test_managed_agent_start_times_out_and_rolls_back_unready_process(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A child that never completes the service handshake cannot survive."""
    manager = ManagedAgentServiceManager(
        startup_timeout_seconds=0.01,
        readiness_poll_seconds=0.001,
    )
    manager.register_service(SubprocessAgentService(_RecordingLauncher()))
    process = _FakeProcess()
    monkeypatch.setattr(
        "server.agent_runtime.subprocess_service.subprocess.Popen",
        lambda *_args, **_kwargs: process,
    )

    with pytest.raises(AgentServiceStartError, match="readiness"):
        asyncio.run(
            manager.start_agents((_launch_request("session-unready"),))
        )

    assert process.terminate_calls == 1
    assert manager.session_statuses() == []


def test_unregistered_service_manager_fails_instead_of_creating_brainless_ai(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ambient module configuration cannot bypass explicit launcher registration."""
    monkeypatch.setenv("DND_EXTERNAL_AGENT_MODULE", "ai.external_agent")
    manager = ManagedAgentServiceManager()

    assert manager.has_service is False
    assert manager.service_id is None
    with pytest.raises(AgentServiceUnavailableError):
        manager.require_service(1)
    with pytest.raises(AgentServiceUnavailableError):
        asyncio.run(
            manager.start_agents((_launch_request("session"),))
        )

    assert manager.session_statuses() == []


def test_launcher_registration_and_unregistration_are_explicit() -> None:
    """One registered service is visible until its exact service id is removed."""
    manager = ManagedAgentServiceManager()
    launcher = _RecordingLauncher()

    manager.register_service(SubprocessAgentService(launcher))

    assert manager.has_service is True
    assert manager.service_id == launcher.service_id
    assert manager.require_service(2).service_id == launcher.service_id
    assert launcher.preflight_counts == [2]

    manager.unregister_service(launcher.service_id)

    assert manager.has_service is False
    assert manager.service_id is None
    with pytest.raises(AgentServiceUnavailableError):
        manager.require_service(1)


def test_registered_launcher_builds_exact_subprocess_argv_and_base_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The supervisor executes only the registered provider's typed process spec."""
    monkeypatch.delenv("DND_GAME_WORKER", raising=False)
    monkeypatch.setenv("TEST_AGENT_PARENT_ENV", "preserved")
    manager = ManagedAgentServiceManager()
    launcher = _RecordingLauncher()
    manager.register_service(SubprocessAgentService(launcher))
    process = _FakeProcess()
    popen_calls: list[tuple[tuple[object, ...], dict[str, Any]]] = []

    def fake_popen(*args: object, **kwargs: Any) -> _FakeProcess:
        popen_calls.append((args, kwargs))
        return process

    monkeypatch.setattr(
        "server.agent_runtime.subprocess_service.subprocess.Popen",
        fake_popen,
    )

    started = _start_with_readiness_ack(
        manager,
        launcher,
        (_launch_request("session-a"),),
    )

    assert len(started) == 1
    assert started[0].status().process_id == process.pid
    assert launcher.preflight_counts == [1]
    assert len(launcher.requests) == 1
    assert launcher.requests[0].session_id == "session-a"
    assert launcher.requests[0].base_url == "http://testserver/runtime/"
    assert launcher.requests[0].spawned_at == 1234.5
    assert launcher.requests[0].readiness_token is not None
    assert len(popen_calls) == 1
    popen_args, popen_kwargs = popen_calls[0]
    assert popen_args == (
        [
            "test-agent",
            "--base-url",
            "http://testserver/runtime",
            "--session-id",
            "session-a",
            "--spawned-at",
            "1234.5",
        ],
    )
    assert popen_kwargs["cwd"] == str(REPOSITORY_ROOT)
    assert popen_kwargs["start_new_session"] is True
    assert popen_kwargs["env"]["PYTHONUNBUFFERED"] == "1"
    assert popen_kwargs["env"]["TEST_AGENT_PARENT_ENV"] == "preserved"
    assert {
        key: value
        for key, value in popen_kwargs["env"].items()
        if key not in {"PYTHONUNBUFFERED"}
    } == {
        key: value
        for key, value in os.environ.items()
        if key not in {"PYTHONUNBUFFERED"}
    }
    assert manager.running_session_ids() == ["session-a"]

    asyncio.run(manager.stop_all())

    assert process.terminate_calls == 1
    assert process.kill_calls == 0
    assert process.wait_timeouts == []
    assert manager.running_session_ids() == []


def test_atomic_batch_spawn_rolls_back_earlier_process_on_later_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A two-side game never retains one live agent after the other fails to spawn."""
    manager = ManagedAgentServiceManager()
    launcher = _RecordingLauncher()
    manager.register_service(SubprocessAgentService(launcher))
    first_process = _FakeProcess()
    popen_count = 0

    def flaky_popen(*_args: object, **_kwargs: Any) -> _FakeProcess:
        nonlocal popen_count
        popen_count += 1
        if popen_count == 1:
            return first_process
        raise OSError("second process refused")

    monkeypatch.setattr(
        "server.agent_runtime.subprocess_service.subprocess.Popen",
        flaky_popen,
    )

    with pytest.raises(AgentServiceStartError, match="second process refused"):
        asyncio.run(
            manager.start_agents((
                _launch_request("session-a"),
                _launch_request("session-b"),
            ))
        )

    assert launcher.preflight_counts == [2]
    assert [request.session_id for request in launcher.requests] == [
        "session-a",
        "session-b",
    ]
    assert all(request.readiness_token for request in launcher.requests)
    assert first_process.terminate_calls == 1
    assert first_process.wait_timeouts == []
    assert manager.session_statuses() == []


def test_unregistering_launcher_stops_every_owned_process(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Composition teardown cannot leave registered service children alive."""
    manager = ManagedAgentServiceManager()
    launcher = _RecordingLauncher()
    manager.register_service(SubprocessAgentService(launcher))
    owned_processes = [_FakeProcess(), _FakeProcess()]
    process_queue = list(owned_processes)

    monkeypatch.setattr(
        "server.agent_runtime.subprocess_service.subprocess.Popen",
        lambda *_args, **_kwargs: process_queue.pop(0),
    )
    _start_with_readiness_ack(
        manager,
        launcher,
        (
            _launch_request("session-a"),
            _launch_request("session-b"),
        ),
    )
    manager.unregister_service(launcher.service_id)

    assert all(process.terminate_calls == 1 for process in owned_processes)
    assert all(process.wait_timeouts == [] for process in owned_processes)
    assert manager.session_statuses() == []
    assert manager.has_service is False


def test_stop_all_escalates_after_terminate_failure_and_stops_every_child(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A failed polite stop still receives kill escalation without skipping peers."""
    manager = ManagedAgentServiceManager()
    launcher = _RecordingLauncher()
    manager.register_service(SubprocessAgentService(launcher))
    stuck = _UnstoppableProcess()
    healthy = _FakeProcess()
    process_queue = [stuck, healthy]
    monkeypatch.setattr(
        "server.agent_runtime.subprocess_service.subprocess.Popen",
        lambda *_args, **_kwargs: process_queue.pop(0),
    )
    _start_with_readiness_ack(
        manager,
        launcher,
        (
            _launch_request("session-stuck"),
            _launch_request("session-healthy"),
        ),
    )

    asyncio.run(manager.stop_all())

    assert stuck.terminate_calls == 1
    assert stuck.kill_calls == 1
    assert healthy.terminate_calls == 1
    assert manager.running_session_ids() == []
    assert manager.is_ready("session-stuck") is False
    assert manager.is_running("session-healthy") is False


def test_isolated_game_server_composition_registers_process_service() -> None:
    """The isolated composition owns its AI command without server-to-ai imports."""
    marker = "__DND_ISOLATED_AGENT_SPEC__="
    script = (
        "import json, sys\n"
        "import ai.isolated_game_server as isolated\n"
        "from server.event_server import agent_service_manager\n"
        "from server.agent_runtime.service import AgentLaunchRequest\n"
        "service = agent_service_manager.require_service(1)\n"
        "builder = isolated.LocalSubjectiveProcessSpecBuilder()\n"
        "spec = builder.build_process_spec(AgentLaunchRequest("
        "session_id='composition-session', "
        "base_url='http://127.0.0.1:8123/', "
        "spawned_at=99.25, "
        "readiness_token='composition-ready-token'))\n"
        f"print({marker!r} + json.dumps({{"
        "'service_id': agent_service_manager.service_id, "
        "'execution_mode': agent_service_manager.execution_mode, "
        "'argv': list(spec.argv), "
        "'cwd': str(spec.cwd)"
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
        "Isolated AI composition failed before exposing its process spec:\n"
        f"stdout:\n{completed.stdout}\n"
        f"stderr:\n{completed.stderr}"
    )
    marker_lines = [
        line for line in completed.stdout.splitlines() if line.startswith(marker)
    ]
    assert len(marker_lines) == 1
    payload = json.loads(marker_lines[0][len(marker):])
    assert payload["service_id"]
    assert payload["execution_mode"] == "isolated_process"
    assert payload["argv"] == [
        sys.executable,
        "-m",
        "ai.external_agent",
        "--base-url",
        "http://127.0.0.1:8123",
        "--session-id",
        "composition-session",
        "--spawned-at",
        "99.25",
        "--readiness-token",
        "composition-ready-token",
    ]
    assert payload["cwd"] == str(REPOSITORY_ROOT)
