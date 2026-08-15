"""In-process HTTP client and runtime reset helpers for server tests."""

from __future__ import annotations

import asyncio
from typing import Any

import httpx

from dnd.runtime_reset import reset_engine_runtime
from server.event_server import app, sim


class ServerTestClient:
    """Reusable synchronous client for the FastAPI app under test."""

    def __init__(self) -> None:
        self._runner: asyncio.Runner | None = None
        self._client: httpx.AsyncClient | None = None

    def get(self, path: str, **kwargs: Any) -> httpx.Response:
        return self._run(self._request("GET", path, **kwargs))

    def post(self, path: str, **kwargs: Any) -> httpx.Response:
        return self._run(self._request("POST", path, **kwargs))

    def close(self) -> None:
        if self._runner is None:
            return
        if self._client is not None:
            self._runner.run(self._client.aclose())
            self._client = None
        self._runner.close()
        self._runner = None

    def __enter__(self) -> "ServerTestClient":
        return self

    def __exit__(
        self,
        exc_type: object,
        exc: object,
        traceback: object,
    ) -> bool:
        self.close()
        return False

    def _run(self, awaitable: Any) -> httpx.Response:
        if self._runner is None:
            self._runner = asyncio.Runner()
        return self._runner.run(awaitable)

    async def _request(
        self,
        method: str,
        path: str,
        **kwargs: Any,
    ) -> httpx.Response:
        if self._client is None:
            self._client = httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app),
                base_url="http://testserver",
            )
        return await self._client.request(method, path, **kwargs)


def reset_server_test_runtime() -> None:
    """Clear engine and standalone-server state between tests."""
    reset_engine_runtime()
    sim.reset()


__all__ = ["ServerTestClient", "reset_server_test_runtime"]
