"""Focused visibility tests for the cold game-directory stream."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from uuid import UUID, uuid4

from starlette.routing import Match

from server import event_server
from server.directory_event_stream import DirectoryEventStream
from server.game_directory.contracts import DirectoryEventRecord


def _event(cursor: int, game_id: UUID | None) -> DirectoryEventRecord:
    """Build one typed lifecycle event for stream filtering."""
    return DirectoryEventRecord(
        cursor=cursor,
        event_id=uuid4(),
        game_id=game_id,
        event_type="game_lifecycle_changed",
        payload={"cursor": cursor},
        payload_digest=f"digest-{cursor}",
        created_at=datetime.now(UTC),
    )


def test_directory_stream_filters_replay_and_live_events() -> None:
    """A subscriber never receives lifecycle rows outside its visibility set."""
    private_game = uuid4()
    visible_game = uuid4()
    history = (_event(1, private_game), _event(2, visible_game))
    stream = DirectoryEventStream(
        lambda since, _limit: tuple(event for event in history if event.cursor > since)
    )

    async def collect() -> tuple[str, str, str]:
        iterator = stream.iterate(
            since=0,
            disconnected=lambda: False,
            event_filter=lambda event: event.game_id == visible_game,
        )
        sync = await anext(iterator)
        replay = await anext(iterator)
        stream.publish(_event(3, private_game))
        stream.publish(_event(4, visible_game))
        live = await anext(iterator)
        await iterator.aclose()
        return sync, replay, live

    sync, replay, live = asyncio.run(collect())
    assert "event: sync" in sync
    assert str(private_game) not in replay
    assert str(visible_game) in replay
    assert str(private_game) not in live
    assert str(visible_game) in live


def test_directory_stream_publishes_every_new_durable_event_once() -> None:
    """A deployment can fan out all newly committed SQLite rows atomically."""

    history: list[DirectoryEventRecord] = []
    stream = DirectoryEventStream(
        lambda since, limit: tuple(
            event for event in history if event.cursor > since
        )[:limit],
    )
    subscription = stream.subscribe()
    history.extend((_event(1, uuid4()), _event(2, uuid4())))

    assert tuple(event.cursor for event in stream.publish_pending()) == (1, 2)
    assert tuple(event.cursor for event in stream.publish_pending()) == ()

    async def collect() -> tuple[int, int]:
        first = await subscription.get()
        second = await subscription.get()
        return first["data"].cursor, second["data"].cursor

    assert asyncio.run(collect()) == (1, 2)


def test_standalone_directory_subscription_precedes_game_id_route() -> None:
    """The literal SSE route must never be parsed as a UUID game identifier."""

    scope = {
        "type": "http",
        "path": "/games/subscribe",
        "method": "GET",
        "root_path": "",
    }
    full_matches = [
        getattr(route, "path", "")
        for route in event_server.app.routes
        if route.matches(scope)[0] is Match.FULL
    ]

    assert full_matches
    assert full_matches[0] == "/games/subscribe"
