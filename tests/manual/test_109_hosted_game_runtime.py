"""Focused checks for isolated workers and database-free runtime authority."""

from __future__ import annotations

import asyncio
import sqlite3
from collections.abc import AsyncIterator, Iterator
from pathlib import Path
from uuid import uuid4

import httpx
import pytest

from server import event_server
from server.arena_mode import ArenaApiClient, reset_standard_arena_runtime
from server.hosted_worker import HostedWorkerManager, HostedWorkerState
from server.runtime_authority import (
    RuntimeAuthorityCache,
    RuntimeAuthorityError,
    RuntimeScope,
    validate_session_binding,
)
from server.worker_proxy import ProxyRouteKind, _relay_response_body, classify_worker_route


@pytest.fixture(autouse=True)
def clean_direct_runtime() -> Iterator[None]:
    """Reset process-global direct-server state around every focused check."""
    reset_standard_arena_runtime()
    yield
    reset_standard_arena_runtime()


def test_hosted_worker_uses_private_socket_and_stops_process_group(tmp_path: Path) -> None:
    """A hosted worker is reachable privately and leaves no live socket."""

    async def exercise() -> None:
        manager = HostedWorkerManager(
            tmp_path / "runtime",
            startup_timeout_seconds=20.0,
        )
        game_id = uuid4()
        placement = await manager.start(
            game_id,
            public_game_base_url=f"http://gateway/games/{game_id}/runtime",
        )

        assert placement.state is HostedWorkerState.READY
        assert Path(placement.socket_path).is_socket()
        async with manager.client(game_id) as client:
            status = await client.get("/game/status")
        assert status.status_code == 200
        assert status.json() == {"active": False, "game": None, "sessions": []}

        stopped = await manager.stop(game_id)
        assert stopped is not None
        assert stopped.state is HostedWorkerState.STOPPED
        assert not Path(placement.socket_path).exists()

    asyncio.run(exercise())


def test_runtime_capability_is_bound_to_game_session_and_entities() -> None:
    """Hot authorization rejects cross-game, cross-session, and cross-entity use."""
    cache = RuntimeAuthorityCache()
    game_id = uuid4()
    other_game_id = uuid4()
    session_id = uuid4()
    controlled_entity_id = uuid4()
    issued = cache.issue(
        hosted_game_id=game_id,
        runtime_session_id=session_id,
        membership_id=uuid4(),
        scopes=[RuntimeScope.OBSERVE, RuntimeScope.CONTROL],
        controlled_entity_uuids=[controlled_entity_id],
        ttl_seconds=60.0,
        now=10.0,
    )

    authority = cache.validate(
        issued.token,
        hosted_game_id=game_id,
        required_scope=RuntimeScope.CONTROL,
        now=20.0,
    )
    validate_session_binding(
        authority,
        path="action/execute",
        query={},
        json_body={
            "session_id": str(session_id),
            "entity_uuid": str(controlled_entity_id),
        },
    )

    with pytest.raises(RuntimeAuthorityError, match="another game"):
        cache.validate(
            issued.token,
            hosted_game_id=other_game_id,
            required_scope=RuntimeScope.CONTROL,
            now=20.0,
        )
    with pytest.raises(RuntimeAuthorityError, match="another runtime session"):
        validate_session_binding(
            authority,
            path="action/execute",
            query={},
            json_body={"session_id": str(uuid4()), "entity_uuid": str(controlled_entity_id)},
        )
    with pytest.raises(RuntimeAuthorityError, match="uncontrolled entity"):
        validate_session_binding(
            authority,
            path="action/execute",
            query={},
            json_body={"session_id": str(session_id), "entity_uuid": str(uuid4())},
        )


def test_public_runtime_route_classifier_blocks_worker_administration() -> None:
    """Only observation, commands, and scoped agent routes can cross the proxy."""
    assert classify_worker_route("GET", "events/subscribe") is ProxyRouteKind.OBSERVE
    assert classify_worker_route("POST", "action/execute") is ProxyRouteKind.COMMAND
    assert classify_worker_route("GET", "ai/sessions/abc/observation/subscribe") is ProxyRouteKind.AGENT
    assert classify_worker_route("POST", "game-creation/start") is ProxyRouteKind.DENIED
    assert classify_worker_route("POST", "simulation/reset") is ProxyRouteKind.DENIED
    assert classify_worker_route("POST", "simulation/pause") is ProxyRouteKind.DENIED
    assert classify_worker_route("POST", "simulation/resume") is ProxyRouteKind.DENIED
    assert classify_worker_route("POST", "simulation/step") is ProxyRouteKind.DENIED
    assert classify_worker_route("POST", "simulation/set-delay") is ProxyRouteKind.DENIED
    assert classify_worker_route("GET", "simulation/status") is ProxyRouteKind.OBSERVE
    assert classify_worker_route("DELETE", "session/abc") is ProxyRouteKind.DENIED


def test_runtime_stream_stops_after_hot_capability_revocation() -> None:
    """An established SSE relay revalidates authority before each chunk."""
    game_id = uuid4()
    session_id = uuid4()
    membership_id = uuid4()
    cache = RuntimeAuthorityCache()
    issued = cache.issue(
        hosted_game_id=game_id,
        runtime_session_id=session_id,
        membership_id=membership_id,
        scopes={RuntimeScope.AGENT},
    )

    class TwoChunkStream(httpx.AsyncByteStream):
        async def __aiter__(self) -> AsyncIterator[bytes]:
            yield b"first"
            yield b"second"

    async def exercise() -> None:
        request = httpx.Request("GET", "http://game-worker/events")
        response = httpx.Response(200, request=request, stream=TwoChunkStream())
        client = httpx.AsyncClient()
        relay = _relay_response_body(
            response,
            client,
            authority_cache=cache,
            runtime_token=issued.token,
            hosted_game_id=game_id,
            required_scope=RuntimeScope.AGENT,
        )
        assert await anext(relay) == b"first"
        cache.revoke(issued.token)
        with pytest.raises(StopAsyncIteration):
            await anext(relay)
        assert client.is_closed

    asyncio.run(exercise())


def test_direct_single_game_server_never_requires_sqlite(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Standalone event_server creates and exposes a game with SQLite disabled."""
    process_starts: list[tuple[str, str]] = []

    def reject_sqlite(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("direct event_server attempted to open SQLite")

    def capture_process_start(session_id: object, base_url: str) -> None:
        process_starts.append((str(session_id), base_url))

    monkeypatch.setattr(sqlite3, "connect", reject_sqlite)
    monkeypatch.setattr(
        event_server.ai_process_manager,
        "start_external_agent",
        capture_process_start,
    )

    request = {
        "scenario": {"kind": "preset", "arena_id": "standard_skeleton_doors"},
        "side_a": {"controller": "human", "name": "Human"},
        "side_b": {"controller": "ai", "name": "AI"},
        "opening_side": "side_a",
    }
    with ArenaApiClient() as client:
        start = client.post("/game-creation/start", json=request)
        events = client.get("/events", params={"since": 0})

    assert start.status_code == 200
    assert start.json()["status"] == "waiting_for_human"
    assert events.status_code == 200
    assert events.json()["generation_id"]
    assert len(process_starts) == 1
