"""Pure ASGI request timing without request-task cancellation cycles."""

from __future__ import annotations

import logging
import time
from typing import cast

from starlette.types import ASGIApp, Message, Receive, Scope, Send


logger = logging.getLogger("dnd_server")


class RequestTimingMiddleware:
    """Record request latency without Starlette's task-spawning base middleware."""

    def __init__(self, app: ASGIApp) -> None:
        """Wrap an ASGI application.

        Args:
            app: Downstream ASGI application.
        """
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Forward one scope and log completed HTTP request latency.

        Args:
            scope: ASGI connection scope.
            receive: ASGI receive callable.
            send: ASGI send callable.
        """
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        started = time.perf_counter()
        status_code: int | str = "error"

        async def send_with_status(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                elapsed_to_headers_ms = (time.perf_counter() - started) * 1000
                headers = list(
                    cast(
                        list[tuple[bytes, bytes]],
                        message.get("headers", []),
                    )
                )
                if not any(name.lower() == b"server-timing" for name, _value in headers):
                    headers.append(
                        (
                            b"server-timing",
                            f"app;dur={elapsed_to_headers_ms:.3f}".encode("ascii"),
                        )
                    )
                message = {**message, "headers": headers}
            await send(message)

        try:
            await self.app(scope, receive, send_with_status)
        finally:
            elapsed_ms = (time.perf_counter() - started) * 1000
            logger.debug(
                "TIMING: %s %s -> %s (%.1fms)",
                scope.get("method", ""),
                scope.get("path", ""),
                status_code,
                elapsed_ms,
            )
