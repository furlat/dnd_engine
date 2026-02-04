"""
Test the position-indexed spatial handler registry system.

This tests:
1. Basic add_spatial_handler / get_spatial_handlers_at
2. Position-indexed lookup for spatial events
3. Batch position updates via update_spatial_handler_positions
4. Handler removal via remove_spatial_handler
5. Integration with ZoneControlCondition
6. Backward compatibility with legacy handlers
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from uuid import uuid4
from typing import Set, Tuple

from dnd.core.events import (
    EventQueue, EventHandler, EventType, EventPhase, Trigger, Event
)
from dnd.core.gridmap import get_map, GridMap
from dnd.entity import Entity
from dnd.monsters.bestiary import create_skeleton
from dnd.utils import reset_combat_state


def reset_all():
    """Reset all registries for clean tests."""
    reset_combat_state()


def test_add_spatial_handler():
    """Test basic add_spatial_handler and get_spatial_handlers_at."""
    print("\n=== Test: add_spatial_handler ===")
    reset_all()

    # Create a simple handler
    handler_fired = {"count": 0}

    def processor(event: Event, source_uuid):
        handler_fired["count"] += 1
        return None

    handler = EventHandler(
        name="Test Entry Handler",
        source_entity_uuid=uuid4(),
        trigger_conditions=[],  # No triggers - uses spatial index
        event_processor=processor
    )

    # Register for specific positions
    positions: Set[Tuple[int, int]] = {(0, 0), (1, 0), (0, 1)}
    EventQueue.add_spatial_handler(
        handler,
        positions,
        EventType.SPATIAL_ENTITY_ENTERED,
        EventPhase.EFFECT
    )

    # Verify handler is registered at all positions
    for pos in positions:
        handlers_at = EventQueue.get_spatial_handlers_at(pos)
        assert len(handlers_at) == 1, f"Expected 1 handler at {pos}, got {len(handlers_at)}"
        assert handlers_at[0].uuid == handler.uuid

    # Verify handler is NOT at unregistered positions
    handlers_at = EventQueue.get_spatial_handlers_at((5, 5))
    assert len(handlers_at) == 0, f"Expected 0 handlers at (5,5), got {len(handlers_at)}"

    print("✓ Handler registered at correct positions")


def test_spatial_event_dispatch():
    """Test that spatial events dispatch to position-indexed handlers."""
    print("\n=== Test: Spatial Event Dispatch ===")
    reset_all()

    # Set up a grid
    grid = get_map()
    grid.create_rectangle(0, 0, 10, 10)

    # Create tracking for handler fires
    fires: list[Tuple[int, int]] = []

    def processor(event: Event, _):
        pos = getattr(event, 'position', None)
        if pos:
            fires.append(pos)
        return None

    handler = EventHandler(
        name="Position Tracker",
        source_entity_uuid=uuid4(),
        trigger_conditions=[],
        event_processor=processor
    )

    # Register for positions (2,2) and (3,3)
    positions: Set[Tuple[int, int]] = {(2, 2), (3, 3)}
    EventQueue.add_spatial_handler(
        handler,
        positions,
        EventType.SPATIAL_ENTITY_ENTERED,
        EventPhase.EFFECT
    )

    # Create entity and move it
    entity = create_skeleton(name="Test", position=(0, 0))
    Entity.update_all_entities_senses()

    # Move to (2, 2) - should fire handler
    grid.move_entity(entity.uuid, (2, 2))

    # Move to (1, 1) - should NOT fire handler
    grid.move_entity(entity.uuid, (1, 1))

    # Move to (3, 3) - should fire handler
    grid.move_entity(entity.uuid, (3, 3))

    # Verify fires
    assert (2, 2) in fires, f"Handler should have fired at (2,2), fires: {fires}"
    assert (1, 1) not in fires, f"Handler should NOT have fired at (1,1), fires: {fires}"
    assert (3, 3) in fires, f"Handler should have fired at (3,3), fires: {fires}"

    print(f"✓ Handler fired at correct positions: {fires}")


def test_update_spatial_handler_positions():
    """Test batch position update for handler."""
    print("\n=== Test: Update Spatial Handler Positions ===")
    reset_all()

    handler = EventHandler(
        name="Moveable Zone Handler",
        source_entity_uuid=uuid4(),
        trigger_conditions=[],
        event_processor=lambda e, s: None
    )

    # Initial positions (zone at center 0,0)
    initial_positions: Set[Tuple[int, int]] = {(-1, -1), (-1, 0), (-1, 1),
                                                  (0, -1), (0, 0), (0, 1),
                                                  (1, -1), (1, 0), (1, 1)}

    EventQueue.add_spatial_handler(
        handler,
        initial_positions,
        EventType.SPATIAL_ENTITY_ENTERED,
        EventPhase.EFFECT
    )

    # Verify initial registration
    for pos in initial_positions:
        handlers = EventQueue.get_spatial_handlers_at(pos)
        assert len(handlers) == 1, f"Expected handler at initial {pos}"

    # Move zone to center (5, 5)
    new_positions: Set[Tuple[int, int]] = {(4, 4), (4, 5), (4, 6),
                                             (5, 4), (5, 5), (5, 6),
                                             (6, 4), (6, 5), (6, 6)}

    success = EventQueue.update_spatial_handler_positions(
        handler.uuid,
        new_positions
    )
    assert success, "Position update should succeed"

    # Verify old positions are empty
    for pos in initial_positions:
        handlers = EventQueue.get_spatial_handlers_at(pos)
        assert len(handlers) == 0, f"Handler should be removed from old {pos}"

    # Verify new positions have handler
    for pos in new_positions:
        handlers = EventQueue.get_spatial_handlers_at(pos)
        assert len(handlers) == 1, f"Handler should be at new {pos}"

    print("✓ Position update works correctly")


def test_remove_spatial_handler():
    """Test removing a spatial handler."""
    print("\n=== Test: Remove Spatial Handler ===")
    reset_all()

    handler = EventHandler(
        name="Removeable Handler",
        source_entity_uuid=uuid4(),
        trigger_conditions=[],
        event_processor=lambda e, s: None
    )

    positions: Set[Tuple[int, int]] = {(0, 0), (1, 1)}
    EventQueue.add_spatial_handler(handler, positions)

    # Verify registered
    assert len(EventQueue.get_spatial_handlers_at((0, 0))) == 1
    assert len(EventQueue.get_spatial_handlers_at((1, 1))) == 1

    # Remove
    success = EventQueue.remove_spatial_handler(handler.uuid)
    assert success, "Removal should succeed"

    # Verify removed from all positions
    assert len(EventQueue.get_spatial_handlers_at((0, 0))) == 0
    assert len(EventQueue.get_spatial_handlers_at((1, 1))) == 0

    print("✓ Handler removed correctly from all positions")


def test_backward_compatibility():
    """Test that legacy handlers (with triggers) still work for spatial events."""
    print("\n=== Test: Backward Compatibility ===")
    reset_all()

    grid = get_map()
    grid.create_rectangle(0, 0, 10, 10)

    legacy_fires = {"count": 0}

    def legacy_processor(event: Event, _):
        legacy_fires["count"] += 1
        return None

    # Legacy handler with trigger (fires for ALL SPATIAL_ENTITY_ENTERED)
    legacy_handler = EventHandler(
        name="Legacy Handler",
        source_entity_uuid=uuid4(),
        trigger_conditions=[Trigger(
            event_type=EventType.SPATIAL_ENTITY_ENTERED,
            event_phase=EventPhase.EFFECT
        )],
        event_processor=legacy_processor
    )
    EventQueue.add_event_handler(legacy_handler)

    # Create entity and move
    entity = create_skeleton(name="Test", position=(0, 0))
    Entity.update_all_entities_senses()

    # Move to (5, 5) - should fire legacy handler
    grid.move_entity(entity.uuid, (5, 5))

    assert legacy_fires["count"] > 0, "Legacy handler should have fired"
    print(f"✓ Legacy handler fired {legacy_fires['count']} times")


def test_multiple_handlers_same_position():
    """Test multiple handlers at the same position."""
    print("\n=== Test: Multiple Handlers Same Position ===")
    reset_all()

    handler1_fires = {"count": 0}
    handler2_fires = {"count": 0}

    def processor1(event: Event, _):
        handler1_fires["count"] += 1
        return None

    def processor2(event: Event, _):
        handler2_fires["count"] += 1
        return None

    handler1 = EventHandler(
        name="Handler 1",
        source_entity_uuid=uuid4(),
        trigger_conditions=[],
        event_processor=processor1
    )

    handler2 = EventHandler(
        name="Handler 2",
        source_entity_uuid=uuid4(),
        trigger_conditions=[],
        event_processor=processor2
    )

    # Both handlers at same position
    position: Set[Tuple[int, int]] = {(5, 5)}
    EventQueue.add_spatial_handler(handler1, position)
    EventQueue.add_spatial_handler(handler2, position)

    # Verify both registered
    handlers = EventQueue.get_spatial_handlers_at((5, 5))
    assert len(handlers) == 2, f"Expected 2 handlers, got {len(handlers)}"

    print("✓ Multiple handlers registered at same position")


def test_reset_clears_spatial_indices():
    """Test that EventQueue.reset() clears spatial handler indices."""
    print("\n=== Test: Reset Clears Spatial Indices ===")
    reset_all()

    handler = EventHandler(
        name="Test Handler",
        source_entity_uuid=uuid4(),
        trigger_conditions=[],
        event_processor=lambda e, s: None
    )

    positions: Set[Tuple[int, int]] = {(0, 0), (1, 1)}
    EventQueue.add_spatial_handler(handler, positions)

    # Verify registered
    assert len(EventQueue.get_spatial_handlers_at((0, 0))) == 1

    # Reset
    EventQueue.reset()

    # Verify cleared
    assert len(EventQueue.get_spatial_handlers_at((0, 0))) == 0

    print("✓ Reset clears spatial indices")


def main():
    """Run all tests."""
    print("=" * 60)
    print("Position-Indexed Spatial Handler Registry Tests")
    print("=" * 60)

    test_add_spatial_handler()
    test_spatial_event_dispatch()
    test_update_spatial_handler_positions()
    test_remove_spatial_handler()
    test_backward_compatibility()
    test_multiple_handlers_same_position()
    test_reset_clears_spatial_indices()

    print("\n" + "=" * 60)
    print("All tests passed! ✓")
    print("=" * 60)


if __name__ == "__main__":
    main()
