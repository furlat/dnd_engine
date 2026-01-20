"""
End-to-end test for websocket event server.

This runs the server and client in the same process to verify everything works.

Usage:
    python -m server.test_websocket
"""

import asyncio
import json
from uuid import uuid4
from typing import List, Dict, Any

import httpx
from fastapi.testclient import TestClient

from server.event_server import app, event_monitor
from dnd.core.gridmap import get_map, reset_map
from dnd.core.events import EventQueue
from dnd.entity import Entity, EntityConfig


def clear_state():
    """Clear all state for fresh test."""
    reset_map()
    Entity._entity_registry.clear()
    Entity._entity_by_position.clear()
    EventQueue._events_by_lineage.clear()
    EventQueue._events_by_uuid.clear()
    EventQueue._events_by_type.clear()
    EventQueue._events_by_timestamp.clear()
    EventQueue._events_by_phase.clear()
    EventQueue._events_by_source.clear()
    EventQueue._events_by_target.clear()
    EventQueue._all_events.clear()
    EventQueue._event_handlers.clear()
    EventQueue._event_handlers_by_trigger.clear()
    EventQueue._event_handlers_by_simple_trigger.clear()
    EventQueue._event_handlers_by_source_entity_uuid.clear()
    EventQueue._on_event_callbacks.clear()


def test_http_endpoints():
    """Test the HTTP endpoints."""
    print("=" * 60)
    print("HTTP ENDPOINTS TEST")
    print("=" * 60)

    clear_state()

    # Start the monitor (simulating lifespan)
    event_monitor.start()

    with TestClient(app) as client:
        # Test root endpoint
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        print(f"✓ GET / : {data}")

        # Test event-types endpoint
        response = client.get("/event-types")
        assert response.status_code == 200
        data = response.json()
        print(f"✓ GET /event-types : {len(data['event_types'])} types, {len(data['phases'])} phases")

        # Generate some events
        grid = get_map()
        grid.create_rectangle(0, 0, 5, 5)

        entity = Entity.create(
            source_entity_uuid=uuid4(),
            name="TestEntity",
            config=EntityConfig(position=(2, 2))
        )

        # Test events endpoint
        response = client.get("/events")
        assert response.status_code == 200
        data = response.json()
        print(f"✓ GET /events : {data['count']} events")

        # Test events with filter
        response = client.get("/events?event_type=spatial_entity_entered")
        assert response.status_code == 200
        data = response.json()
        print(f"✓ GET /events?event_type=spatial_entity_entered : {data['count']} events")

    event_monitor.stop()
    print("\n✓ All HTTP endpoints work")
    return True


def test_websocket_connection():
    """Test websocket connection and event receiving."""
    print("\n" + "=" * 60)
    print("WEBSOCKET CONNECTION TEST")
    print("=" * 60)

    clear_state()
    event_monitor.start()

    received_events: List[Dict[str, Any]] = []

    with TestClient(app) as client:
        with client.websocket_connect("/ws") as websocket:
            # Should receive connection message
            data = websocket.receive_json()
            assert data["type"] == "connected"
            print(f"✓ Connected: {data['message']}")

            # Generate events
            grid = get_map()
            grid.create_rectangle(0, 0, 5, 5)

            entity = Entity.create(
                source_entity_uuid=uuid4(),
                name="TestEntity",
                config=EntityConfig(position=(2, 2))
            )
            print("✓ Created entity at (2, 2)")

            # Should receive spatial event
            data = websocket.receive_json()
            assert data["type"] == "event"
            received_events.append(data["event"])
            print(f"✓ Received event: {data['event']['event_type']}")

            # Move entity
            Entity.update_entity_position(entity, (3, 3))
            print("✓ Moved entity to (3, 3)")

            # Should receive two events (left and entered)
            data = websocket.receive_json()
            received_events.append(data["event"])
            print(f"✓ Received event: {data['event']['event_type']}")

            data = websocket.receive_json()
            received_events.append(data["event"])
            print(f"✓ Received event: {data['event']['event_type']}")

            # Test ping
            websocket.send_json({"type": "ping"})
            data = websocket.receive_json()
            assert data["type"] == "pong"
            print("✓ Ping/pong works")

    event_monitor.stop()

    print(f"\n✓ Received {len(received_events)} events total")
    return True


def test_websocket_filter():
    """Test websocket event filtering."""
    print("\n" + "=" * 60)
    print("WEBSOCKET FILTER TEST")
    print("=" * 60)

    clear_state()
    event_monitor.start()

    with TestClient(app) as client:
        with client.websocket_connect("/ws") as websocket:
            # Get connection message
            websocket.receive_json()

            # Set filter for only entered events
            websocket.send_json({
                "type": "filter",
                "event_types": ["spatial_entity_entered"]
            })
            data = websocket.receive_json()
            assert data["type"] == "filter_set"
            print(f"✓ Filter set: {data['event_types']}")

            # Generate events
            grid = get_map()
            grid.create_rectangle(0, 0, 5, 5)

            entity = Entity.create(
                source_entity_uuid=uuid4(),
                name="TestEntity",
                config=EntityConfig(position=(2, 2))
            )

            # Should receive entered event
            data = websocket.receive_json()
            assert data["event"]["event_type"] == "spatial_entity_entered"
            print(f"✓ Received filtered event: {data['event']['event_type']}")

            # Move entity - should only get entered, not left
            Entity.update_entity_position(entity, (3, 3))

            # Next event should be entered (left is filtered out)
            data = websocket.receive_json()
            assert data["event"]["event_type"] == "spatial_entity_entered"
            print(f"✓ Received filtered event: {data['event']['event_type']}")

    event_monitor.stop()
    print("\n✓ Event filtering works")
    return True


def test_get_history():
    """Test getting event history through websocket."""
    print("\n" + "=" * 60)
    print("WEBSOCKET HISTORY TEST")
    print("=" * 60)

    clear_state()
    event_monitor.start()

    # Generate some events first
    grid = get_map()
    grid.create_rectangle(0, 0, 5, 5)

    entity = Entity.create(
        source_entity_uuid=uuid4(),
        name="TestEntity",
        config=EntityConfig(position=(2, 2))
    )

    Entity.update_entity_position(entity, (3, 3))

    print(f"Generated {len(EventQueue._all_events)} events before connecting")

    with TestClient(app) as client:
        with client.websocket_connect("/ws") as websocket:
            # Get connection message
            websocket.receive_json()

            # Request history
            websocket.send_json({
                "type": "get_history",
                "limit": 10
            })

            # Collect history events
            history_events = []
            # Use a timeout approach - collect until we get all events
            import time
            start = time.time()
            while time.time() - start < 2.0:  # 2 second timeout
                try:
                    # Non-blocking receive with short timeout
                    data = websocket.receive_json()
                    if data["type"] == "event":
                        history_events.append(data["event"])
                except:
                    break

            print(f"✓ Received {len(history_events)} history events")
            for event in history_events:
                print(f"  - {event['event_type']}: {event.get('position', 'N/A')}")

    event_monitor.stop()
    return len(history_events) > 0


def main():
    """Run all tests."""
    print("=" * 60)
    print("WEBSOCKET SERVER END-TO-END TEST")
    print("=" * 60)

    results = [
        test_http_endpoints(),
        test_websocket_connection(),
        test_websocket_filter(),
    ]

    print("\n" + "=" * 60)
    print("FINAL RESULTS")
    print("=" * 60)
    passed = sum(results)
    total = len(results)
    print(f"{passed}/{total} tests passed")

    return all(results)


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
