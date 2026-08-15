"""Focused HTTP, SSE, and authority checks for objective diagnostics."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncGenerator, Iterator, Mapping
from typing import cast
from uuid import uuid4

import pytest
from fastapi import HTTPException
from fastapi.responses import Response
from starlette.requests import Request

from dnd.core.combat_log import CombatLogEntry, CombatLogEntryType
from dnd.core.events import Event, EventPhase, EventQueue, EventType
from dnd.encounter import Encounter
from dnd.runtime_reset import reset_engine_runtime
from server.event_server import (
    app,
    build_current_objective_world,
    get_objective_diagnostics_bootstrap,
    get_objective_diagnostics_combat_log,
    get_objective_diagnostics_events,
    sim,
    subscribe_objective_diagnostics,
)
from server.event_stream import event_stream
from server.timeline_contracts import CombatLogProjection


_OBJECTIVE_DIAGNOSTICS_PATHS = (
    "/diagnostics/objective/bootstrap",
    "/diagnostics/objective/events",
    "/diagnostics/objective/combat-log",
    "/diagnostics/objective/subscribe",
)


def _request(
    path: str,
    *,
    headers: Mapping[str, str] | None = None,
) -> Request:
    encoded_headers = [
        (key.lower().encode("ascii"), value.encode("ascii"))
        for key, value in (headers or {}).items()
    ]
    return Request({
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": path,
        "raw_path": path.encode("ascii"),
        "query_string": b"",
        "headers": encoded_headers,
        "client": ("127.0.0.1", 1),
        "server": ("testserver", 80),
    })


async def _call_objective_diagnostics_route(
    path: str,
    *,
    headers: Mapping[str, str] | None = None,
) -> object:
    """Call one objective route and close accepted streams after their sync."""
    request = _request(path, headers=headers)
    if path == "/diagnostics/objective/bootstrap":
        return await get_objective_diagnostics_bootstrap(
            request=request,
            response=Response(),
        )
    if path == "/diagnostics/objective/events":
        return await get_objective_diagnostics_events(
            request=request,
            response=Response(),
            from_cursor=0,
            through_cursor=None,
            limit=None,
            expected_source_stream_id=None,
            expected_generation_id=None,
        )
    if path == "/diagnostics/objective/combat-log":
        return await get_objective_diagnostics_combat_log(
            request=request,
            response=Response(),
            from_cursor=0,
            through_cursor=None,
            limit=None,
            expected_source_stream_id=None,
            expected_generation_id=None,
        )
    if path == "/diagnostics/objective/subscribe":
        response = await subscribe_objective_diagnostics(
            request=request,
            since_event=0,
            since_log=0,
            expected_source_stream_id=None,
            expected_generation_id=None,
        )
        iterator = cast(AsyncGenerator[str, None], response.body_iterator)
        try:
            await anext(iterator)
        finally:
            await iterator.aclose()
        return response
    raise AssertionError(f"Unrecognized objective diagnostics path: {path}")


@pytest.fixture
def objective_scene(
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[tuple[Encounter, Event, CombatLogEntry]]:
    """Install one exact completion/log pair in a local objective timeline."""
    sim.reset()
    reset_engine_runtime(grid_size=(3, 3))
    event_stream.ensure_attached()
    event_stream._clear_source_journal()

    encounter = Encounter(name="Objective diagnostics", source_entity_uuid=uuid4())
    sim.encounter = encounter
    Encounter._active_encounter = encounter
    completion = Event(
        name="Objective completion",
        source_entity_uuid=uuid4(),
        event_type=EventType.BASE_ACTION,
        phase=EventPhase.COMPLETION,
        use_register=False,
    )
    entry = CombatLogEntry(
        entry_type=CombatLogEntryType.ACTION,
        source_name="Archivist",
        source_uuid=str(completion.source_entity_uuid),
        compact="Archivist acts",
        verbose="Archivist acts",
        detailed="Archivist acts",
    )
    encounter.combat_log.append(entry)
    completion.use_register = True
    event_stream._on_combat_log(encounter, 0, entry, completion)
    EventQueue.register(completion)

    try:
        yield encounter, completion, entry
    finally:
        sim.reset()
        reset_engine_runtime(grid_size=(3, 3))
        event_stream.ensure_attached()


def test_objective_http_routes_share_cold_identity_and_exact_cursors(
    objective_scene: tuple[Encounter, Event, CombatLogEntry],
) -> None:
    """Bootstrap, events, and logs describe one reducer-complete timeline."""
    encounter, _completion, entry = objective_scene
    request = _request("/diagnostics/objective/bootstrap")
    bootstrap_response = Response()
    events_response = Response()
    logs_response = Response()

    bootstrap = asyncio.run(get_objective_diagnostics_bootstrap(
        request=request,
        response=bootstrap_response,
    ))
    events = asyncio.run(get_objective_diagnostics_events(
        request=request,
        response=events_response,
        from_cursor=0,
        through_cursor=None,
        limit=None,
        expected_source_stream_id=bootstrap.source_stream_id,
        expected_generation_id=bootstrap.generation_id,
    ))
    logs = asyncio.run(get_objective_diagnostics_combat_log(
        request=request,
        response=logs_response,
        from_cursor=0,
        through_cursor=None,
        limit=None,
        expected_source_stream_id=bootstrap.source_stream_id,
        expected_generation_id=bootstrap.generation_id,
    ))

    assert bootstrap.source_stream_id == str(encounter.uuid)
    assert bootstrap.projection == "objective"
    assert bootstrap.event_cursor == events.total == 1
    assert bootstrap.combat_log_cursor == logs.total == 1
    assert bootstrap.world.state.encounter is not None
    assert bootstrap.world.state.encounter.uuid == str(encounter.uuid)
    assert bootstrap.world.equipment_by_entity == {}
    assert events.source_stream_id == logs.source_stream_id == bootstrap.source_stream_id
    assert events.generation_id == logs.generation_id == bootstrap.generation_id
    assert events.frames[0].combat_log_cursor == 1
    cold_event = events.frames[0].event.model_dump(mode="json")
    assert cold_event["wire_type"] == "dnd.core.events.Event"
    assert cold_event["phase"] == "completion"
    assert logs.projection is CombatLogProjection.OBJECTIVE
    assert logs.frames[0].entry is not None
    assert logs.frames[0].entry.compact == entry.compact
    assert logs.frames[0].entry is not entry
    for response in (bootstrap_response, events_response, logs_response):
        assert response.headers["cache-control"] == "private, no-store"


def test_repeated_objective_backfill_uses_the_same_frozen_event_bytes(
    objective_scene: tuple[Encounter, Event, CombatLogEntry],
) -> None:
    """Backfill never reserializes a mutable EventQueue object."""
    _encounter, completion, _entry = objective_scene
    request = _request("/diagnostics/objective/events")

    first = asyncio.run(get_objective_diagnostics_events(
        request=request,
        response=Response(),
        from_cursor=0,
        through_cursor=None,
        limit=None,
        expected_source_stream_id=None,
        expected_generation_id=None,
    ))
    first_bytes = first.model_dump_json().encode("utf-8")

    completion.name = "mutated after objective freeze"
    completion.children_events.append(uuid4())
    second = asyncio.run(get_objective_diagnostics_events(
        request=request,
        response=Response(),
        from_cursor=0,
        through_cursor=None,
        limit=None,
        expected_source_stream_id=first.source_stream_id,
        expected_generation_id=first.generation_id,
    ))

    assert second.model_dump_json().encode("utf-8") == first_bytes
    assert second.frames[0].event.model_dump(mode="json")["name"] == (
        "Objective completion"
    )


def _parse_sse(frame: str) -> tuple[str, dict[str, object]]:
    event = next(
        line.removeprefix("event: ")
        for line in frame.splitlines()
        if line.startswith("event: ")
    )
    data = "\n".join(
        line.removeprefix("data: ")
        for line in frame.splitlines()
        if line.startswith("data: ")
    )
    return event, json.loads(data)


def _publish_objective_pair(
    encounter: Encounter,
    *,
    label: str,
) -> tuple[Event, CombatLogEntry]:
    """Append one exact event/log pair through the live source journal."""
    event = Event(
        name=label,
        source_entity_uuid=uuid4(),
        event_type=EventType.BASE_ACTION,
        phase=EventPhase.COMPLETION,
        use_register=False,
    )
    entry = CombatLogEntry(
        entry_type=CombatLogEntryType.ACTION,
        source_name="Archivist",
        source_uuid=str(event.source_entity_uuid),
        compact=label,
        verbose=label,
        detailed=label,
    )
    log_index = len(encounter.combat_log)
    encounter.combat_log.append(entry)
    event.use_register = True
    event_stream._on_combat_log(encounter, log_index, entry, event)
    EventQueue.register(event)
    return event, entry


def test_objective_sse_emits_only_sync_event_and_log_frames(
    objective_scene: tuple[Encounter, Event, CombatLogEntry],
) -> None:
    """The diagnostics stream has no player session, ping, or heartbeat model."""

    async def collect_initial_frames() -> tuple[Response, list[str]]:
        response = await subscribe_objective_diagnostics(
            request=_request("/diagnostics/objective/subscribe"),
            since_event=0,
            since_log=0,
            expected_source_stream_id=None,
            expected_generation_id=None,
        )
        iterator = cast(AsyncGenerator[str, None], response.body_iterator)
        frames: list[str] = []
        try:
            for _ in range(3):
                frames.append(await anext(iterator))
        finally:
            await iterator.aclose()
        return response, frames

    response, raw_frames = asyncio.run(collect_initial_frames())
    parsed = [_parse_sse(frame) for frame in raw_frames]

    assert response.headers["cache-control"] == "private, no-store"
    assert [event for event, _payload in parsed] == [
        "sync",
        "game_event",
        "combat_log",
    ]
    sync = parsed[0][1]
    assert "session" not in sync
    assert "server_time" not in sync
    assert "event" not in sync
    assert sync["projection"] == "objective"
    event_payload = cast(dict[str, object], parsed[1][1]["event"])
    assert event_payload["phase"] == "completion"
    assert parsed[2][1]["projection"] == "objective"


def test_objective_bootstrap_retries_a_crossed_event_driven_world_mutation(
    objective_scene: tuple[Encounter, Event, CombatLogEntry],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """World and cursors are accepted only after one unchanged source boundary."""
    encounter, _completion, _entry = objective_scene
    initial_round = encounter.round_number
    build_calls = 0

    def mutate_after_first_world_capture(*, encounter: Encounter | None):
        nonlocal build_calls
        build_calls += 1
        world = build_current_objective_world(encounter=encounter)
        if build_calls == 1:
            assert encounter is not None
            encounter.round_number = initial_round + 1
            Event(
                name="Mutation crossing bootstrap",
                source_entity_uuid=uuid4(),
                event_type=EventType.BASE_ACTION,
                phase=EventPhase.COMPLETION,
            )
        return world

    monkeypatch.setattr(
        "server.event_server.build_current_objective_world",
        mutate_after_first_world_capture,
    )

    bootstrap = asyncio.run(get_objective_diagnostics_bootstrap(
        request=_request("/diagnostics/objective/bootstrap"),
        response=Response(),
    ))

    assert build_calls == 2
    assert bootstrap.event_cursor == EventQueue.event_cursor() == 2
    assert bootstrap.combat_log_cursor == len(encounter.combat_log) == 1
    assert bootstrap.world.state.encounter is not None
    assert bootstrap.world.state.encounter.round_number == initial_round + 1


def test_objective_sse_subscribe_barrier_has_no_duplicate_or_gap_under_append(
    objective_scene: tuple[Encounter, Event, CombatLogEntry],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An append after subscribe but before capture is backfill-only, then live continues."""
    encounter, _completion, _entry = objective_scene
    original_capture = event_stream._capture_objective_source_snapshot
    interleaved = False

    def append_during_capture(*args, **kwargs):
        nonlocal interleaved
        if not interleaved:
            interleaved = True
            _publish_objective_pair(encounter, label="At barrier")
        return original_capture(*args, **kwargs)

    monkeypatch.setattr(
        event_stream,
        "_capture_objective_source_snapshot",
        append_during_capture,
    )

    async def collect() -> list[tuple[str, dict[str, object]]]:
        response = await subscribe_objective_diagnostics(
            request=_request("/diagnostics/objective/subscribe"),
            since_event=0,
            since_log=0,
            expected_source_stream_id=None,
            expected_generation_id=None,
        )
        _publish_objective_pair(encounter, label="After barrier")
        iterator = cast(AsyncGenerator[str, None], response.body_iterator)
        frames: list[str] = []
        try:
            for _ in range(7):
                frames.append(await anext(iterator))
        finally:
            await iterator.aclose()
        return [_parse_sse(frame) for frame in frames]

    parsed = asyncio.run(collect())

    assert interleaved is True
    assert [event for event, _payload in parsed] == [
        "sync",
        "game_event",
        "combat_log",
        "game_event",
        "combat_log",
        "game_event",
        "combat_log",
    ]
    assert [
        payload["event_cursor"]
        for event, payload in parsed
        if event == "game_event"
    ] == [1, 2, 3]
    assert [
        payload["combat_log_cursor"]
        for event, payload in parsed
        if event == "combat_log"
    ] == [1, 2, 3]
    assert cast(dict[str, object], parsed[0][1])["event_cursor"] == 2
    assert cast(dict[str, object], parsed[0][1])["combat_log_cursor"] == 2


def test_objective_sse_live_delivery_never_recaptures_full_log_prefix(
    objective_scene: tuple[Encounter, Event, CombatLogEntry],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Live envelopes carry exact barriers, so only reconnect reads cold history."""
    encounter, _completion, _entry = objective_scene

    async def collect() -> list[tuple[str, dict[str, object]]]:
        response = await subscribe_objective_diagnostics(
            request=_request("/diagnostics/objective/subscribe"),
            since_event=0,
            since_log=0,
            expected_source_stream_id=None,
            expected_generation_id=None,
        )
        iterator = cast(AsyncGenerator[str, None], response.body_iterator)
        frames: list[str] = []
        try:
            for _ in range(3):
                frames.append(await anext(iterator))

            def reject_live_history_capture(*args, **kwargs):
                raise AssertionError("live delivery recaptured objective history")

            monkeypatch.setattr(
                event_stream,
                "capture_objective_source_snapshot",
                reject_live_history_capture,
            )
            monkeypatch.setattr(
                event_stream,
                "capture_combat_log_source_window",
                reject_live_history_capture,
            )
            _publish_objective_pair(encounter, label="Live O(1)")
            frames.append(await anext(iterator))
            frames.append(await anext(iterator))
        finally:
            await iterator.aclose()
        return [_parse_sse(frame) for frame in frames]

    parsed = asyncio.run(collect())

    assert [event for event, _payload in parsed] == [
        "sync",
        "game_event",
        "combat_log",
        "game_event",
        "combat_log",
    ]
    assert parsed[-2][1]["event_cursor"] == 2
    assert parsed[-1][1]["combat_log_cursor"] == 2


def test_objective_sse_closes_on_generation_change(
    objective_scene: tuple[Encounter, Event, CombatLogEntry],
) -> None:
    """An open diagnostics stream never silently rebinds to a new generation."""

    async def observe_reset() -> None:
        response = await subscribe_objective_diagnostics(
            request=_request("/diagnostics/objective/subscribe"),
            since_event=1,
            since_log=1,
            expected_source_stream_id=None,
            expected_generation_id=None,
        )
        iterator = cast(AsyncGenerator[str, None], response.body_iterator)
        try:
            sync = _parse_sse(await anext(iterator))
            assert sync[0] == "sync"
            EventQueue.reset()
            event_stream.ensure_attached()
            with pytest.raises(StopAsyncIteration):
                await anext(iterator)
        finally:
            await iterator.aclose()

    asyncio.run(observe_reset())


def test_objective_sse_closes_on_source_stream_change(
    objective_scene: tuple[Encounter, Event, CombatLogEntry],
) -> None:
    """An event from a replacement encounter cannot enter the bound stream."""

    async def observe_replacement() -> None:
        response = await subscribe_objective_diagnostics(
            request=_request("/diagnostics/objective/subscribe"),
            since_event=1,
            since_log=1,
            expected_source_stream_id=None,
            expected_generation_id=None,
        )
        iterator = cast(AsyncGenerator[str, None], response.body_iterator)
        try:
            sync = _parse_sse(await anext(iterator))
            assert sync[0] == "sync"
            replacement = Encounter(
                name="Replacement objective source",
                source_entity_uuid=uuid4(),
            )
            sim.encounter = replacement
            Encounter._active_encounter = replacement
            with pytest.raises(StopAsyncIteration):
                await anext(iterator)
        finally:
            await iterator.aclose()

    asyncio.run(observe_replacement())


def test_objective_diagnostics_routes_replace_legacy_objective_aliases() -> None:
    """OpenAPI contains one live objective route family and no raw history aliases."""
    paths = app.openapi()["paths"]
    assert {
        "/diagnostics/objective/bootstrap",
        "/diagnostics/objective/events",
        "/diagnostics/objective/combat-log",
        "/diagnostics/objective/subscribe",
        "/diagnostics/subjective-parity",
    }.issubset(paths)
    for legacy_path in (
        "/state",
        "/visibility",
        "/events",
        "/events/history",
        "/events/subscribe",
        "/combat-log",
        "/replication/v2/events/history",
    ):
        assert legacy_path not in paths


def test_standalone_objective_diagnostics_allow_header_free_access(
    objective_scene: tuple[Encounter, Event, CombatLogEntry],
) -> None:
    """Direct standalone development can inspect every objective route."""
    for path in _OBJECTIVE_DIAGNOSTICS_PATHS:
        result = asyncio.run(_call_objective_diagnostics_route(path))
        assert result is not None


def test_objective_history_rejects_stale_source_identity(
    objective_scene: tuple[Encounter, Event, CombatLogEntry],
) -> None:
    """Recovery never silently crosses an encounter or generation boundary."""
    with pytest.raises(HTTPException) as stale_source:
        asyncio.run(get_objective_diagnostics_events(
            request=_request("/diagnostics/objective/events"),
            response=Response(),
            from_cursor=0,
            through_cursor=None,
            limit=None,
            expected_source_stream_id="another-encounter",
            expected_generation_id=None,
        ))
    assert stale_source.value.status_code == 409
    stale_detail = cast(dict[str, object], stale_source.value.detail)
    assert stale_detail["code"] == "objective_diagnostics_source_changed"
