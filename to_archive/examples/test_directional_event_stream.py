#!/usr/bin/env python
"""Focused server payload tests for tile-owned directional spatial events.

Run with:
    python examples/test_directional_event_stream.py
"""

import json
import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dnd.core.events import EventQueue, EventType, SpatialChangeEvent
from dnd.core.gridmap import get_map
from dnd.utils import reset_combat_state
from server.event_server import app
from server.event_stream import event_stream, format_sse, make_stream_id


def check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)
    print(f"  PASSED: {message}")


def sse_data(frame: str) -> dict:
    data_lines = [
        line.removeprefix("data: ")
        for line in frame.splitlines()
        if line.startswith("data: ")
    ]
    return json.loads("\n".join(data_lines))


def setup_directional_event() -> int:
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 3, 3)
    cursor = EventQueue.event_cursor()
    changed = grid.set_tile_directional_border((1, 1), "vision", "east", False)
    check(changed, "directional border setter reports a change")
    return cursor


def directional_tile_events_since(cursor: int) -> list[SpatialChangeEvent]:
    return [
        event for _, event in EventQueue.iter_events_since(cursor)
        if isinstance(event, SpatialChangeEvent)
        and event.event_type == EventType.SPATIAL_TILE_CHANGED
    ]


def test_event_history_endpoint_directional_fields() -> None:
    print("\nTEST: /events includes directional spatial metadata")
    cursor = setup_directional_event()

    with TestClient(app) as client:
        response = client.get(f"/events?since={cursor}&limit=0")

    check(response.status_code == 200, "/events returns 200")
    payload = response.json()
    spatial_events = [
        event for event in payload["events"]
        if event["event_type"] == "spatial_tile_changed"
    ]
    check(bool(spatial_events), "/events returns the directional tile event")

    event = spatial_events[-1]
    check(event["directional_position"] == [1, 1], "/events serializes directional_position as JSON array")
    check(event["directional_directions"] == ["east"], "/events carries changed direction")
    check(event["directional_channels"] == ["vision"], "/events carries changed channel")
    check(event["directional_blocks_vision"]["east"] is True, "/events carries directional vision block map")
    check(event["event_type"] == "spatial_tile_changed", "/events uses existing spatial event type")


def test_sse_game_event_directional_fields() -> None:
    print("\nTEST: SSE game_event frame includes directional spatial metadata")
    cursor = setup_directional_event()
    event_stream.ensure_attached()

    payloads = [
        payload for payload in event_stream.iter_game_events_since(cursor, None)
        if payload.event.event_type == EventType.SPATIAL_TILE_CHANGED
    ]
    check(bool(payloads), "event stream builds a game_event payload for directional tile change")

    payload = payloads[-1]
    frame = format_sse(
        "game_event",
        payload,
        make_stream_id(payload.event_cursor, payload.combat_log_cursor),
    )
    data = sse_data(frame)

    check("event: game_event" in frame, "SSE frame keeps the game_event envelope")
    check(data["event"]["directional_position"] == [1, 1], "SSE serializes directional_position as JSON array")
    check(data["event"]["directional_directions"] == ["east"], "SSE carries changed direction")
    check(data["event"]["directional_channels"] == ["vision"], "SSE carries changed channel")
    check(data["event"]["directional_blocks_vision"]["east"] is True, "SSE carries directional vision block map")
    check(data["event"]["event_type"] == "spatial_tile_changed", "SSE uses existing spatial event type")


def main() -> None:
    print("=" * 70)
    print("Directional Event Stream Tests")
    print("=" * 70)
    test_event_history_endpoint_directional_fields()
    test_sse_game_event_directional_fields()
    print("\nALL DIRECTIONAL EVENT STREAM TESTS PASSED")


if __name__ == "__main__":
    main()
