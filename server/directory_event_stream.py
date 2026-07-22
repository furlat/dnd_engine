"""Bounded lifecycle stream for active and historical game-directory changes."""

from __future__ import annotations

import asyncio
import inspect
import time
from collections.abc import AsyncGenerator, Awaitable, Callable, Sequence

from pydantic import BaseModel, Field

from server.event_stream import BoundedSubscription, format_sse
from server.game_directory.contracts import DirectoryEventRecord


class DirectoryStreamSync(BaseModel):
    """Initial directory-stream cursor."""

    cursor: int = Field(ge=0, description="Latest durable directory-event cursor.")


class DirectoryStreamHeartbeat(BaseModel):
    """Directory-stream keepalive payload."""

    cursor: int = Field(ge=0, description="Latest durable directory-event cursor.")
    server_time: float = Field(description="Current gateway Unix timestamp.")


class DirectoryEventStream:
    """Fan out durable lifecycle records with bounded subscriber queues."""

    def __init__(self, history_loader: Callable[[int, int], Sequence[DirectoryEventRecord]]) -> None:
        """Create a stream around one durable event-history loader."""
        self._history_loader = history_loader
        self._subscriptions: list[BoundedSubscription] = []
        self._cursor = 0

    @property
    def cursor(self) -> int:
        """Return latest lifecycle cursor observed by this gateway process."""
        return self._cursor

    def publish(self, event: DirectoryEventRecord) -> None:
        """Publish one already-durable directory event to live subscribers."""
        self._cursor = max(self._cursor, event.cursor)
        envelope = {"event": "directory_event", "data": event, "id": str(event.cursor)}
        for subscription in list(self._subscriptions):
            if not subscription.try_enqueue(envelope):
                self.unsubscribe(subscription)

    def subscribe(self, max_depth: int = 256) -> BoundedSubscription:
        """Create one bounded live directory subscription."""
        subscription = BoundedSubscription(max_depth=max_depth)
        self._subscriptions.append(subscription)
        return subscription

    def unsubscribe(self, subscription: BoundedSubscription) -> None:
        """Remove one live subscription idempotently."""
        if subscription in self._subscriptions:
            self._subscriptions.remove(subscription)

    async def iterate(
        self,
        *,
        since: int,
        disconnected: Callable[[], Awaitable[bool] | bool],
        event_filter: Callable[[DirectoryEventRecord], bool] | None = None,
        heartbeat_seconds: float = 10.0,
    ) -> AsyncGenerator[str, None]:
        """Yield authorized sync, replay, live, heartbeat, and eviction frames."""
        subscription = self.subscribe()
        try:
            yield format_sse("sync", DirectoryStreamSync(cursor=self._cursor), str(self._cursor))
            for event in self._history_loader(since, 1000):
                self._cursor = max(self._cursor, event.cursor)
                if event_filter is not None and not event_filter(event):
                    continue
                yield format_sse("directory_event", event, str(event.cursor))

            while True:
                if await _is_disconnected(disconnected):
                    return
                try:
                    envelope = await asyncio.wait_for(
                        subscription.get(),
                        timeout=heartbeat_seconds,
                    )
                except asyncio.TimeoutError:
                    yield format_sse(
                        "heartbeat",
                        DirectoryStreamHeartbeat(cursor=self._cursor, server_time=time.time()),
                        str(self._cursor),
                    )
                    continue
                if (
                    envelope["event"] == "directory_event"
                    and isinstance(envelope["data"], DirectoryEventRecord)
                    and event_filter is not None
                    and not event_filter(envelope["data"])
                ):
                    continue
                yield format_sse(
                    str(envelope["event"]),
                    envelope["data"],
                    str(envelope["id"]) if envelope["id"] is not None else None,
                )
                if envelope["event"] == "evicted":
                    return
        finally:
            self.unsubscribe(subscription)


async def _is_disconnected(callback: Callable[[], Awaitable[bool] | bool]) -> bool:
    """Resolve synchronous or asynchronous disconnect callbacks."""
    result = callback()
    if inspect.isawaitable(result):
        return bool(await result)
    return bool(result)
