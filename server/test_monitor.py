"""
In-process test for EventMonitor.

This tests the EventMonitor directly without needing a websocket connection.
Useful for debugging the event capture mechanism.

Usage:
    python -m server.test_monitor
"""

import asyncio
from uuid import uuid4
from typing import List, Dict, Any

from dnd.core.gridmap import get_map, reset_map
from dnd.core.events import EventQueue, EventType
from dnd.entity import Entity, EntityConfig

# Import the monitor
from server.event_server import EventMonitor


def clear_state():
    """Clear all state for fresh test."""
    reset_map()
    Entity._entity_registry.clear()
    Entity._entity_by_position.clear()
    # Clear event queue
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


async def test_event_monitor():
    """Test that EventMonitor captures events correctly."""
    print("=" * 60)
    print("EVENT MONITOR TEST")
    print("=" * 60)

    clear_state()

    # Create monitor and listener queue
    monitor = EventMonitor()
    event_queue: asyncio.Queue = asyncio.Queue()
    monitor.add_listener(event_queue)

    # Start monitoring
    monitor.start()
    print(f"\n✓ Monitor started")

    # Create grid
    grid = get_map()
    grid.create_rectangle(0, 0, 10, 10)
    print("✓ Created 10x10 grid")

    # Create entity (should generate spatial events)
    entity_uuid = uuid4()
    entity = Entity.create(
        source_entity_uuid=entity_uuid,
        name="TestEntity",
        config=EntityConfig(position=(2, 2))
    )
    print("✓ Created entity at (2, 2)")

    # Give async queue time to receive
    await asyncio.sleep(0.1)

    # Check what events were captured
    captured_events: List[Dict[str, Any]] = []
    while not event_queue.empty():
        event_data = event_queue.get_nowait()
        captured_events.append(event_data)

    print(f"\n✓ Captured {len(captured_events)} events from entity creation")
    for event in captured_events:
        print(f"  - {event['event_type']}: {event.get('position', 'N/A')}")

    # Move entity (should generate more events)
    captured_events.clear()

    Entity.update_entity_position(entity, (3, 3))
    print("\n✓ Moved entity to (3, 3)")

    await asyncio.sleep(0.1)

    while not event_queue.empty():
        event_data = event_queue.get_nowait()
        captured_events.append(event_data)

    print(f"✓ Captured {len(captured_events)} events from movement")
    for event in captured_events:
        et = event['event_type']
        pos = event.get('position', 'N/A')
        old_pos = event.get('old_position', 'N/A')
        print(f"  - {et}: pos={pos}, old_pos={old_pos}")

    # Move again
    captured_events.clear()

    Entity.update_entity_position(entity, (5, 5))
    print("\n✓ Moved entity to (5, 5)")

    await asyncio.sleep(0.1)

    while not event_queue.empty():
        event_data = event_queue.get_nowait()
        captured_events.append(event_data)

    print(f"✓ Captured {len(captured_events)} events from second movement")
    for event in captured_events:
        et = event['event_type']
        pos = event.get('position', 'N/A')
        print(f"  - {et}: pos={pos}")

    # Stop monitoring
    monitor.stop()
    print("\n✓ Monitor stopped")

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Total events in EventQueue: {len(EventQueue._all_events)}")
    print(f"Events by type:")
    for et in EventType:
        count = len(EventQueue.get_events_by_type(et))
        if count > 0:
            print(f"  - {et.value}: {count}")

    return True


async def test_multiple_listeners():
    """Test that multiple listeners all receive events."""
    print("\n" + "=" * 60)
    print("MULTIPLE LISTENERS TEST")
    print("=" * 60)

    clear_state()

    monitor = EventMonitor()

    # Create multiple listener queues
    queues = [asyncio.Queue() for _ in range(3)]
    for q in queues:
        monitor.add_listener(q)

    print(f"✓ Added {len(queues)} listeners")

    monitor.start()

    # Create grid and entity
    grid = get_map()
    grid.create_rectangle(0, 0, 5, 5)

    _ = Entity.create(
        source_entity_uuid=uuid4(),
        name="TestEntity",
        config=EntityConfig(position=(1, 1))
    )

    await asyncio.sleep(0.1)

    # Check each queue received events
    counts = []
    for i, q in enumerate(queues):
        count = 0
        while not q.empty():
            q.get_nowait()
            count += 1
        counts.append(count)
        print(f"  Listener {i+1}: received {count} events")

    monitor.stop()

    # All listeners should receive same number of events
    if len(set(counts)) == 1 and counts[0] > 0:
        print("✓ All listeners received same events")
        return True
    else:
        print("✗ Listeners received different event counts")
        return False


async def test_event_data_structure():
    """Test the structure of captured event data."""
    print("\n" + "=" * 60)
    print("EVENT DATA STRUCTURE TEST")
    print("=" * 60)

    clear_state()

    monitor = EventMonitor()
    event_queue: asyncio.Queue = asyncio.Queue()
    monitor.add_listener(event_queue)
    monitor.start()

    # Generate an event
    grid = get_map()
    grid.create_rectangle(0, 0, 5, 5)

    Entity.create(
        source_entity_uuid=uuid4(),
        name="TestEntity",
        config=EntityConfig(position=(2, 2))
    )

    await asyncio.sleep(0.1)

    # Get first event and inspect
    if not event_queue.empty():
        event_data = event_queue.get_nowait()

        print("Event data structure:")
        print(f"  Type: {type(event_data)}")
        print(f"  Keys: {list(event_data.keys())}")

        # Check required fields
        required = ['uuid', 'event_type', 'phase', 'timestamp', 'source_entity_uuid']
        for field in required:
            if field in event_data:
                print(f"  ✓ {field}: {str(event_data[field])[:50]}")
            else:
                print(f"  ✗ {field}: MISSING")

        # Check it's JSON serializable
        import json
        try:
            json_str = json.dumps(event_data)
            print(f"  ✓ JSON serializable ({len(json_str)} chars)")
        except Exception as e:
            print(f"  ✗ JSON error: {e}")

    monitor.stop()
    return True


async def main():
    """Run all tests."""
    results = []

    results.append(await test_event_monitor())
    results.append(await test_multiple_listeners())
    results.append(await test_event_data_structure())

    print("\n" + "=" * 60)
    print("FINAL RESULTS")
    print("=" * 60)
    passed = sum(results)
    total = len(results)
    print(f"{passed}/{total} tests passed")

    return all(results)


if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)
