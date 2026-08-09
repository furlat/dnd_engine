"""Focused checks for isolated workers and database-free runtime authority."""

from __future__ import annotations

import asyncio
import os
import sqlite3
from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import cast
from uuid import uuid4

import httpx
import pytest
from fastapi import HTTPException
from starlette.requests import Request

from server import event_server
from tests.manual.server_test_client import (
    ServerTestClient,
    reset_server_test_runtime,
)
from server.hosted_worker import (
    HostedWorkerAssignment,
    HostedWorkerManager,
    HostedWorkerState,
)
from server.game_directory.contracts import (
    MembershipCapabilities,
    MembershipRecord,
    MembershipRole,
)
from server.game_gateway import _runtime_scopes
from server.runtime_authority import (
    RuntimeAuthorityCache,
    RuntimeAuthorityError,
    RuntimeScope,
    parse_runtime_projection_authority,
    runtime_projection_headers,
    validate_session_binding,
)
from server.worker_proxy import (
    ProxyRouteKind,
    _forward_request_headers,
    _relay_response_body,
    classify_worker_route,
    proxy_runtime_request,
)
from server.player_replication_contract import SubjectiveBootstrapDeferred


@pytest.fixture(autouse=True)
def clean_direct_runtime() -> Iterator[None]:
    """Reset process-global direct-server state around every focused check."""
    reset_server_test_runtime()
    yield
    reset_server_test_runtime()


def test_hosted_worker_configuration_rejection_is_structured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A public process rejects the private configure route with typed detail."""
    monkeypatch.delenv("DND_GAME_WORKER", raising=False)
    assignment = HostedWorkerAssignment(
        hosted_game_id=uuid4(),
        public_game_base_url="http://gateway/games/example/runtime",
        worker_instance_id=uuid4(),
        worker_generation=1,
        terminal_runtime_directory="/private/worker/runtime",
    )

    with pytest.raises(HTTPException) as rejected:
        asyncio.run(event_server.configure_hosted_worker(assignment))

    assert rejected.value.status_code == 404
    assert rejected.value.detail == {
        "code": "hosted_worker_configuration_unavailable",
        "message": "Hosted worker configuration is unavailable",
    }


def test_hosted_worker_configuration_uses_typed_process_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Warm-worker assignment never mutates process environment identity."""
    monkeypatch.setenv("DND_GAME_WORKER", "1")
    retired_environment_keys = (
        "DND_HOSTED_GAME_ID",
        "DND_PUBLIC_GAME_BASE_URL",
        "DND_WORKER_INSTANCE_ID",
        "DND_WORKER_GENERATION",
        "DND_WORKER_RUNTIME_DIR",
    )
    for key in retired_environment_keys:
        monkeypatch.delenv(key, raising=False)
    assignment = HostedWorkerAssignment(
        hosted_game_id=uuid4(),
        public_game_base_url="http://gateway/games/example/runtime",
        worker_instance_id=uuid4(),
        worker_generation=3,
        terminal_runtime_directory="/private/worker/runtime",
    )

    assert asyncio.run(
        event_server.configure_hosted_worker(assignment),
    ) == {"status": "configured"}
    assert event_server._require_hosted_worker_assignment() == assignment
    assert all(key not in os.environ for key in retired_environment_keys)


def test_hosted_worker_uses_private_socket_and_stops_process_group(tmp_path: Path) -> None:
    """A hosted worker is reachable privately and leaves no live socket."""

    async def exercise() -> None:
        manager = HostedWorkerManager(tmp_path / "runtime")
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
        assert status.json() == {
            "active": False,
            "game_id": None,
            "encounter_active": False,
            "active_entity_uuid": None,
            "sessions": [],
            "creation": None,
    }

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
    validate_session_binding(
        authority,
        path=f"entity/{controlled_entity_id}/available-actions",
        query={"session_id": str(session_id)},
        json_body=None,
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
    with pytest.raises(RuntimeAuthorityError, match="uncontrolled entity"):
        validate_session_binding(
            authority,
            path=f"entity/{uuid4()}/equippable-items",
            query={"session_id": str(session_id)},
            json_body=None,
        )


def test_runtime_projection_headers_preserve_trusted_subjective_authority() -> None:
    """The private worker hop receives projection claims, never the bearer token."""
    cache = RuntimeAuthorityCache()
    game_id = uuid4()
    session_id = uuid4()
    membership_id = uuid4()
    controlled_entity_id = uuid4()
    issued = cache.issue(
        hosted_game_id=game_id,
        runtime_session_id=session_id,
        membership_id=membership_id,
        scopes=[RuntimeScope.OBSERVE, RuntimeScope.SUBJECTIVE_OBSERVE],
        controlled_entity_uuids=[controlled_entity_id],
        authority_epoch=7,
    )

    headers = runtime_projection_headers(issued.authority)
    projected = parse_runtime_projection_authority(headers)

    assert projected is not None
    assert projected.hosted_game_id == game_id
    assert projected.runtime_session_id == session_id
    assert projected.membership_id == membership_id
    assert projected.authority_epoch == 7
    assert projected.scopes == frozenset({RuntimeScope.OBSERVE, RuntimeScope.SUBJECTIVE_OBSERVE})
    assert projected.controlled_entity_uuids == frozenset({controlled_entity_id})
    assert projected.observer_entity_uuids == frozenset({controlled_entity_id})
    assert projected.active_observer_uuid == controlled_entity_id
    assert "authorization" not in headers

    request = Request({
        "type": "http",
        "method": "GET",
        "path": "/replication/bootstrap",
        "query_string": b"",
        "headers": [
            (b"authorization", b"Bearer secret"),
            (b"x-dnd-runtime-session-id", b"spoofed"),
            (b"x-client-header", b"preserved"),
        ],
    })
    forwarded = _forward_request_headers(request, authority=issued.authority)
    assert forwarded["x-dnd-runtime-session-id"] == str(session_id)
    assert forwarded["x-client-header"] == "preserved"
    assert "authorization" not in forwarded


def test_runtime_scope_mapping_authorizes_explicit_subjective_observer_union() -> None:
    """Public observers get subjective scope without gaining entity control."""
    common = {
        "game_id": uuid4(),
        "principal_id": uuid4(),
        "joined_at": datetime.now(UTC),
    }
    participant = MembershipRecord(
        **common,
        role=MembershipRole.PLAYER,
        capabilities=MembershipCapabilities(
            may_connect=True,
            may_observe_public_state=True,
            may_observe_subjective_state=True,
            may_control_entities=True,
        ),
    )
    observer = MembershipRecord(
        **common,
        role=MembershipRole.OBSERVER,
        capabilities=MembershipCapabilities(
            may_connect=True,
            may_observe_public_state=True,
            may_observe_subjective_state=True,
        ),
    )
    administrator = MembershipRecord(
        **common,
        role=MembershipRole.REFEREE,
        capabilities=MembershipCapabilities(
            may_connect=True,
            may_manage_game=True,
        ),
    )

    assert RuntimeScope.SUBJECTIVE_OBSERVE in _runtime_scopes(participant)
    assert RuntimeScope.SUBJECTIVE_OBSERVE in _runtime_scopes(observer)
    assert RuntimeScope.CONTROL not in _runtime_scopes(observer)
    assert RuntimeScope.ADMINISTER in _runtime_scopes(administrator)
    assert RuntimeScope.ADMINISTER not in _runtime_scopes(observer)


def test_public_runtime_route_classifier_blocks_worker_administration() -> None:
    """Objective diagnostics cross only the explicit administration partition."""
    assert classify_worker_route("GET", "events/subscribe") is ProxyRouteKind.DENIED
    assert classify_worker_route("GET", "events") is ProxyRouteKind.DENIED
    assert classify_worker_route("GET", "events/history") is ProxyRouteKind.DENIED
    assert classify_worker_route("GET", "combat-log") is ProxyRouteKind.DENIED
    for route in (
        "replication/bootstrap",
        "replication/frames",
        "replication/combat-log",
        "replication/subscribe",
    ):
        assert classify_worker_route("GET", route) is ProxyRouteKind.SUBJECTIVE
        assert classify_worker_route("HEAD", route) is ProxyRouteKind.SUBJECTIVE
        assert classify_worker_route("POST", route) is ProxyRouteKind.DENIED
    for route in (
        "diagnostics/objective/bootstrap",
        "diagnostics/objective/events",
        "diagnostics/objective/combat-log",
        "diagnostics/objective/subscribe",
        "diagnostics/subjective-parity",
    ):
        assert classify_worker_route("GET", route) is ProxyRouteKind.ADMINISTER
        assert classify_worker_route("HEAD", route) is ProxyRouteKind.ADMINISTER
        assert classify_worker_route("POST", route) is ProxyRouteKind.DENIED
    assert classify_worker_route("GET", "diagnostics/objective/private") is ProxyRouteKind.DENIED
    for raw_route in ("state", "visibility", "entities", "grid", "encounter", "entity/abc", "tile/1/2"):
        assert classify_worker_route("GET", raw_route) is ProxyRouteKind.DENIED
    for controlled_route in (
        "entity/abc/available-actions",
        "entity/abc/equippable-items",
        "entity/abc/handlers",
    ):
        assert classify_worker_route("GET", controlled_route) is ProxyRouteKind.COMMAND
        assert classify_worker_route("HEAD", controlled_route) is ProxyRouteKind.COMMAND
    assert classify_worker_route("GET", "entity/abc/equipment") is ProxyRouteKind.DENIED
    for forbidden_replication_route in (
        "replication",
        "replication/v2/bootstrap",
        "replication/v2/combat-log",
        "replication/v2/events/history",
        "replication/v2/events/subscribe",
        "replication/private",
    ):
        assert (
            classify_worker_route("GET", forbidden_replication_route)
            is ProxyRouteKind.DENIED
        )
    assert classify_worker_route("POST", "action/execute") is ProxyRouteKind.COMMAND
    assert classify_worker_route("GET", "ai/sessions/abc/observation/subscribe") is ProxyRouteKind.AGENT
    assert classify_worker_route("POST", "game-creation/start") is ProxyRouteKind.DENIED
    assert classify_worker_route("POST", "simulation/reset") is ProxyRouteKind.DENIED
    assert classify_worker_route("POST", "simulation/pause") is ProxyRouteKind.DENIED
    assert classify_worker_route("POST", "simulation/resume") is ProxyRouteKind.DENIED
    assert classify_worker_route("POST", "simulation/step") is ProxyRouteKind.DENIED
    assert classify_worker_route("POST", "simulation/set-delay") is ProxyRouteKind.DENIED
    assert classify_worker_route("GET", "simulation/status") is ProxyRouteKind.DENIED
    assert classify_worker_route("GET", "game/status") is ProxyRouteKind.DENIED
    assert classify_worker_route("DELETE", "session/abc") is ProxyRouteKind.DENIED


def test_objective_diagnostics_proxy_requires_administer_before_worker_io() -> None:
    """An observe-only runtime token is rejected before opening the worker UDS."""
    game_id = uuid4()
    cache = RuntimeAuthorityCache()
    issued = cache.issue(
        hosted_game_id=game_id,
        runtime_session_id=uuid4(),
        membership_id=uuid4(),
        scopes={RuntimeScope.OBSERVE},
    )

    class RejectWorkerIO:
        def socket_path(self, _game_id: object) -> Path:
            raise AssertionError("authorization failure reached worker I/O")

    async def receive() -> dict[str, object]:
        return {"type": "http.request", "body": b"", "more_body": False}

    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/games/game/runtime/diagnostics/objective/bootstrap",
            "query_string": b"",
            "headers": [
                (b"authorization", f"Bearer {issued.token}".encode("ascii")),
            ],
        },
        receive=receive,
    )
    response = asyncio.run(proxy_runtime_request(
        request,
        hosted_game_id=game_id,
        worker_path="diagnostics/objective/bootstrap",
        worker_manager=cast(HostedWorkerManager, RejectWorkerIO()),
        authority_cache=cache,
    ))

    assert response.status_code == 403
    assert b"runtime_authority_rejected" in response.body


def test_hosted_bootstrap_proxy_preserves_typed_source_batch_deferral(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The gateway relays the worker's closed 409 body without wrapping it."""
    game_id = uuid4()
    session_id = uuid4()
    observer_uuid = uuid4()
    cache = RuntimeAuthorityCache()
    issued = cache.issue(
        hosted_game_id=game_id,
        runtime_session_id=session_id,
        membership_id=uuid4(),
        scopes={RuntimeScope.SUBJECTIVE_OBSERVE},
        controlled_entity_uuids=(observer_uuid,),
        observer_entity_uuids=(observer_uuid,),
        active_observer_uuid=observer_uuid,
    )
    deferral = SubjectiveBootstrapDeferred(
        source_stream_id="worker-stream",
        generation_id="worker-generation",
    )

    class DeferredWorkerClient:
        def __init__(self, *args: object, **kwargs: object) -> None:
            del args, kwargs

        def build_request(
            self,
            method: str,
            path: str,
            *,
            headers: dict[str, str],
            content: bytes,
        ) -> httpx.Request:
            return httpx.Request(
                method,
                f"http://game-worker{path}",
                headers=headers,
                content=content,
            )

        async def send(
            self,
            request: httpx.Request,
            *,
            stream: bool,
        ) -> httpx.Response:
            assert stream is True
            return httpx.Response(
                409,
                request=request,
                content=deferral.model_dump_json().encode("utf-8"),
                headers={
                    "content-type": "application/json",
                    "cache-control": "private, no-store",
                },
            )

        async def aclose(self) -> None:
            return None

    class DeferredWorkerManager:
        def socket_path(self, _game_id: object) -> Path:
            return Path("/tmp/dnd-engine-deferred-worker.sock")

    async def receive() -> dict[str, object]:
        return {"type": "http.request", "body": b"", "more_body": False}

    monkeypatch.setattr(httpx, "AsyncClient", DeferredWorkerClient)
    request = Request(
        {
            "type": "http",
            "method": "GET",
            "scheme": "http",
            "server": ("gateway", 80),
            "path": "/games/game/runtime/replication/bootstrap",
            "query_string": f"session_id={session_id}".encode("ascii"),
            "headers": [
                (b"authorization", f"Bearer {issued.token}".encode("ascii")),
            ],
        },
        receive=receive,
    )
    response = asyncio.run(
        proxy_runtime_request(
            request,
            hosted_game_id=game_id,
            worker_path="replication/bootstrap",
            worker_manager=cast(HostedWorkerManager, DeferredWorkerManager()),
            authority_cache=cache,
        )
    )

    assert response.status_code == 409
    assert response.body == deferral.model_dump_json().encode("utf-8")
    assert response.headers["cache-control"] == "private, no-store"


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
    def reject_sqlite(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("direct event_server attempted to open SQLite")

    monkeypatch.setattr(sqlite3, "connect", reject_sqlite)

    with ServerTestClient() as client:
        composed = client.post(
            "/game-creation/compose",
            json={
                "title": "Direct Server Test",
                "roster_slots": [
                    {
                        "roster_slot_id": "players",
                        "roster": {
                            "kind": "authored_roster",
                            "roster_id": "hero.fighter_l5_shield_torch",
                        },
                        "faction_id": "players",
                        "deployment_zone_id": "zone_1",
                        "controller_defaults": {
                            "controller": "human",
                            "participant_name": "Human",
                            "policy_id": None,
                            "member_overrides": [],
                        },
                    },
                    {
                        "roster_slot_id": "opposition",
                        "roster": {
                            "kind": "authored_roster",
                            "roster_id": "monsters.skeleton_trio",
                        },
                        "faction_id": "opposition",
                        "deployment_zone_id": "zone_2",
                        "controller_defaults": {
                            "controller": "ai",
                            "participant_name": "AI",
                            "policy_id": "builtin.basic",
                            "member_overrides": [],
                        },
                    },
                ],
                "battlefield_id": "battlefield.open_floor_bright",
                "deployment_id": "neutral.battlefield.open_floor_bright",
                "opening_policy": {
                    "kind": "fixed_roster",
                    "roster_slot_id": "players",
                },
            },
        )
        assert composed.status_code == 200, composed.text
        normalized = composed.json()
        start = client.post(
            "/game-creation/start",
            json={
                "expected_content_set_digest": normalized[
                    "content_set_digest"
                ],
                "expected_ruleset_digest": normalized["ruleset_digest"],
                "recipe": normalized["recipe"],
            },
        )
        events = client.get(
            "/diagnostics/objective/events",
            params={"from_cursor": 0},
        )

    assert start.status_code == 200
    assert start.json()["status"] == "prepared"
    opposition = start.json()["rosters"][1]["entity_assignments"]
    assert all(row["policy_id"] == "builtin.basic" for row in opposition)
    assert all(row["policy_execution"] == "in_process" for row in opposition)
    assert all(row["provider_id"] is None for row in opposition)
    assert events.status_code == 200
    assert events.json()["generation_id"]
    assert events.json()["source_stream_id"]
    assert event_server.sim.get_session_manager().sessions == {}
