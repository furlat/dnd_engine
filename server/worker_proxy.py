"""Transparent HTTP and SSE proxying from a game route to one hot worker."""

from __future__ import annotations

import json
from enum import Enum
from typing import AsyncIterator
from uuid import UUID

import httpx
from fastapi import Request
from fastapi.responses import Response, StreamingResponse

from server.hosted_worker import HostedWorkerManager
from server.runtime_authority import (
    RUNTIME_PROJECTION_HEADER_PREFIX,
    RuntimeAuthority,
    RuntimeAuthorityCache,
    RuntimeAuthorityError,
    RuntimeScope,
    extract_bearer_token,
    runtime_projection_headers,
    validate_session_binding,
)


class ProxyRouteKind(str, Enum):
    """Authorization family for a worker route."""

    OBSERVE = "observe"
    SUBJECTIVE = "subjective"
    COMMAND = "command"
    AGENT = "agent"
    ADMINISTER = "administer"
    DENIED = "denied"


_HOP_BY_HOP_HEADERS = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
}

_DENIED_PREFIXES = (
    "game-creation/",
    "session/create",
    "game/join",
    "mapeditor/",
    "game/evidence/",
)

_RAW_PLAYER_REPLICATION_ROUTES = frozenset({
    "combat-log",
    "events",
    "events/history",
    "events/subscribe",
})

_PLAYER_REPLICATION_ROUTES = frozenset({
    "replication/bootstrap",
    "replication/frames",
    "replication/combat-log",
    "replication/subscribe",
})

_OBJECTIVE_DIAGNOSTICS_ROUTES = frozenset({
    "diagnostics/objective/bootstrap",
    "diagnostics/objective/events",
    "diagnostics/objective/combat-log",
    "diagnostics/objective/subscribe",
    "diagnostics/subjective-parity",
})

_CONTROLLED_ENTITY_READ_SUFFIXES = frozenset({
    "available-actions",
    "equippable-items",
    "handlers",
})


def classify_worker_route(method: str, path: str) -> ProxyRouteKind:
    """Classify a public game-scoped worker route without reading SQLite."""
    normalized = path.strip("/")
    upper_method = method.upper()
    if any(normalized == prefix.rstrip("/") or normalized.startswith(prefix) for prefix in _DENIED_PREFIXES):
        return ProxyRouteKind.DENIED
    if normalized == "simulation" or normalized.startswith("simulation/"):
        return ProxyRouteKind.DENIED
    if upper_method == "DELETE" and normalized.startswith("session/"):
        return ProxyRouteKind.DENIED
    if normalized in _RAW_PLAYER_REPLICATION_ROUTES:
        return ProxyRouteKind.DENIED
    if normalized in _PLAYER_REPLICATION_ROUTES:
        return (
            ProxyRouteKind.SUBJECTIVE
            if upper_method in {"GET", "HEAD"}
            else ProxyRouteKind.DENIED
        )
    if normalized == "replication" or normalized.startswith("replication/"):
        return ProxyRouteKind.DENIED
    if normalized in _OBJECTIVE_DIAGNOSTICS_ROUTES:
        return (
            ProxyRouteKind.ADMINISTER
            if upper_method in {"GET", "HEAD"}
            else ProxyRouteKind.DENIED
        )
    if normalized == "diagnostics/objective" or normalized.startswith(
        "diagnostics/objective/"
    ):
        return ProxyRouteKind.DENIED
    path_parts = [part for part in normalized.split("/") if part]
    if (
        upper_method in {"GET", "HEAD"}
        and len(path_parts) == 3
        and path_parts[0] == "entity"
        and path_parts[2] in _CONTROLLED_ENTITY_READ_SUFFIXES
    ):
        return ProxyRouteKind.COMMAND
    if normalized == "ai/sessions":
        return ProxyRouteKind.DENIED
    if normalized.startswith("ai/sessions/"):
        return ProxyRouteKind.AGENT
    if normalized == "ai/policy/source" and upper_method in {"GET", "HEAD"}:
        return ProxyRouteKind.AGENT
    if (
        upper_method == "POST"
        and len(path_parts) == 4
        and path_parts[:2] == ["ai", "takeover"]
        and path_parts[3] == "heartbeat"
    ):
        return ProxyRouteKind.AGENT
    if normalized.startswith("ai/takeover"):
        return ProxyRouteKind.DENIED
    if normalized.startswith("action/"):
        return ProxyRouteKind.COMMAND
    if upper_method in {"POST", "PUT", "PATCH", "DELETE"} and (
        normalized.startswith("entity/")
    ):
        return ProxyRouteKind.COMMAND
    if (
        upper_method == "POST"
        and len(path_parts) == 3
        and path_parts[0] == "session"
        and path_parts[2] == "ping"
    ):
        return ProxyRouteKind.OBSERVE
    return ProxyRouteKind.DENIED


async def proxy_runtime_request(
    request: Request,
    *,
    hosted_game_id: UUID,
    worker_path: str,
    worker_manager: HostedWorkerManager,
    authority_cache: RuntimeAuthorityCache,
) -> Response:
    """Authorize and forward one runtime request to the selected worker."""
    route_kind = classify_worker_route(request.method, worker_path)
    if route_kind is ProxyRouteKind.DENIED:
        return _error_response(403, "worker_route_not_public", "Worker route is not public")

    required_scope = {
        ProxyRouteKind.OBSERVE: RuntimeScope.OBSERVE,
        ProxyRouteKind.SUBJECTIVE: RuntimeScope.SUBJECTIVE_OBSERVE,
        ProxyRouteKind.COMMAND: RuntimeScope.CONTROL,
        ProxyRouteKind.AGENT: RuntimeScope.AGENT,
        ProxyRouteKind.ADMINISTER: RuntimeScope.ADMINISTER,
    }[route_kind]
    try:
        token = extract_bearer_token(request.headers.get("authorization"))
        authority = authority_cache.validate(
            token,
            hosted_game_id=hosted_game_id,
            required_scope=required_scope,
        )
        body = await request.body()
        json_body = _decode_json_body(body, request.headers.get("content-type"))
        validate_session_binding(
            authority,
            path=worker_path,
            query=dict(request.query_params),
            json_body=json_body,
        )
    except RuntimeAuthorityError as exc:
        return _error_response(403, "runtime_authority_rejected", str(exc))

    socket_path = worker_manager.socket_path(hosted_game_id)
    transport = httpx.AsyncHTTPTransport(uds=str(socket_path))
    client = httpx.AsyncClient(
        transport=transport,
        base_url="http://game-worker",
        timeout=httpx.Timeout(None),
    )
    target_path = "/" + worker_path.lstrip("/")
    if request.url.query:
        target_path = f"{target_path}?{request.url.query}"
    worker_request = client.build_request(
        request.method,
        target_path,
        headers=_forward_request_headers(request, authority=authority),
        content=body,
    )
    try:
        worker_response = await client.send(worker_request, stream=True)
    except httpx.HTTPError as exc:
        await client.aclose()
        return _error_response(502, "worker_unavailable", str(exc))

    headers = _forward_response_headers(worker_response)
    content_type = worker_response.headers.get("content-type", "")
    if content_type.startswith("text/event-stream"):
        return StreamingResponse(
            _relay_response_body(
                worker_response,
                client,
                authority_cache=authority_cache,
                runtime_token=token,
                hosted_game_id=hosted_game_id,
                required_scope=required_scope,
            ),
            status_code=worker_response.status_code,
            headers=headers,
            media_type="text/event-stream",
        )

    try:
        content = await worker_response.aread()
    finally:
        await worker_response.aclose()
        await client.aclose()
    return Response(
        content=content,
        status_code=worker_response.status_code,
        headers=headers,
        media_type=None,
    )


async def _relay_response_body(
    response: httpx.Response,
    client: httpx.AsyncClient,
    *,
    authority_cache: RuntimeAuthorityCache,
    runtime_token: str,
    hosted_game_id: UUID,
    required_scope: RuntimeScope,
) -> AsyncIterator[bytes]:
    """Relay streaming bytes while the runtime capability remains valid."""
    try:
        async for chunk in response.aiter_raw():
            try:
                authority_cache.validate(
                    runtime_token,
                    hosted_game_id=hosted_game_id,
                    required_scope=required_scope,
                )
            except RuntimeAuthorityError:
                return
            yield chunk
    finally:
        await response.aclose()
        await client.aclose()


def _decode_json_body(body: bytes, content_type: str | None) -> object | None:
    """Decode a JSON body only when its media type declares JSON."""
    if not body or content_type is None or "json" not in content_type.lower():
        return None
    try:
        return json.loads(body)
    except json.JSONDecodeError:
        return None


def _forward_request_headers(
    request: Request,
    *,
    authority: RuntimeAuthority,
) -> dict[str, str]:
    """Copy end-to-end headers and install trusted private-hop authority."""
    forwarded = {
        key: value
        for key, value in request.headers.items()
        if key.lower() not in _HOP_BY_HOP_HEADERS
        and key.lower() not in {"host", "content-length", "authorization"}
        and not key.lower().startswith(RUNTIME_PROJECTION_HEADER_PREFIX)
    }
    forwarded.update(runtime_projection_headers(authority))
    return forwarded


def _forward_response_headers(response: httpx.Response) -> dict[str, str]:
    """Copy end-to-end response headers without transport framing."""
    return {
        key: value
        for key, value in response.headers.items()
        if key.lower() not in _HOP_BY_HOP_HEADERS
        and key.lower() not in {"content-length", "content-type"}
    }


def _error_response(status_code: int, code: str, message: str) -> Response:
    """Return one typed gateway error envelope."""
    return Response(
        content=json.dumps({"detail": {"code": code, "message": message}}),
        status_code=status_code,
        media_type="application/json",
    )
