"""
Test client for the event websocket server.

This script:
1. Connects to the websocket server
2. Listens for events
3. Optionally generates test events by creating entities/moving them

Usage:
    # First, start the server in another terminal:
    uv run python -m server.event_server

    # Then run this client:
    uv run python -m server.test_client
"""

import asyncio
import json
import sys
from uuid import uuid4

try:
    import websockets
except ImportError:
    print("websockets package not installed. Install with: pip install websockets")
    sys.exit(1)


async def listen_for_events(uri: str = "ws://localhost:8000/ws"):
    """Connect to websocket and listen for events."""
    print(f"Connecting to {uri}...")

    try:
        async with websockets.connect(uri) as websocket:
            print("Connected!")

            response = await websocket.recv()
            data = json.loads(response)
            print(f"Server: {data}")

            print("\nListening for events (Ctrl+C to stop)...\n")

            while True:
                try:
                    message = await websocket.recv()
                    data = json.loads(message)

                    if data.get("type") == "event":
                        event = data["event"]
                        print(f"[{event['event_type']}] {event['name']} "
                              f"(phase: {event['phase']}, uuid: {event['uuid'][:8]}...)")

                        if "position" in event:
                            print(f"    position: {event['position']}")
                        if event.get("status_message"):
                            print(f"    message: {event['status_message']}")
                    else:
                        print(f"Message: {data}")

                except websockets.ConnectionClosed:
                    print("Connection closed by server")
                    break

    except ConnectionRefusedError:
        print(f"Could not connect to {uri}")
        print("Make sure the server is running: uv run python -m server.event_server")
        sys.exit(1)


async def test_with_filter(uri: str = "ws://localhost:8000/ws"):
    """Test with event type filter."""
    print(f"Connecting to {uri} with filter...")

    async with websockets.connect(uri) as websocket:

        await websocket.recv()
        print("Connected!")

        await websocket.send(json.dumps({
            "type": "filter",
            "event_types": ["spatial_entity_entered", "spatial_entity_left"]
        }))

        response = await websocket.recv()
        print(f"Filter response: {json.loads(response)}")

        print("\nListening for spatial events only...\n")

        for _ in range(10):
            try:
                message = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                data = json.loads(message)
                if data.get("type") == "event":
                    event = data["event"]
                    print(f"[{event['event_type']}] position: {event.get('position')}")
            except asyncio.TimeoutError:
                print("No events received in 5 seconds")
                break


async def generate_test_events():
    """Generate test events by creating and moving entities."""
    print("Generating test events...")

    from dnd.core.gridmap import get_map, reset_map
    from dnd.entity import Entity, EntityConfig

    reset_map()
    Entity._entity_registry.clear()
    Entity._entity_by_position.clear()

    grid = get_map()
    grid.create_rectangle(0, 0, 10, 10)
    print("Created 10x10 grid")

    entity_uuid = uuid4()
    entity = Entity.create(
        source_entity_uuid=entity_uuid,
        name="TestEntity",
        config=EntityConfig(position=(2, 2))
    )
    print(f"Created entity at (2, 2)")

    await asyncio.sleep(0.5)
    Entity.update_entity_position(entity, (3, 3))
    print("Moved entity to (3, 3)")

    await asyncio.sleep(0.5)
    Entity.update_entity_position(entity, (4, 4))
    print("Moved entity to (4, 4)")

    await asyncio.sleep(0.5)
    Entity.update_entity_position(entity, (5, 5))
    print("Moved entity to (5, 5)")

    print("\nDone generating events")


async def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="WebSocket test client")
    parser.add_argument("--generate", action="store_true",
                        help="Generate test events (requires server in same process)")
    parser.add_argument("--filter", action="store_true",
                        help="Test with event filter")
    parser.add_argument("--uri", default="ws://localhost:8000/ws",
                        help="WebSocket URI")
    args = parser.parse_args()

    if args.generate:

        await generate_test_events()
    elif args.filter:
        await test_with_filter(args.uri)
    else:
        await listen_for_events(args.uri)

if __name__ == "__main__":
    asyncio.run(main())
