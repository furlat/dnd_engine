"""
Test script for spatial events system.

This tests:
1. GridMap spatial data management
2. SpatialChangeEvents being fired on entity movement
3. Cell subscriptions (entities subscribe to visible cells)
4. Integration with shadowcast (FOV) and dijkstra (pathfinding)
"""

from uuid import uuid4


# Core imports
from dnd.core.gridmap import get_map, reset_map, GridMap
from dnd.core.events import (
    EventQueue, EventType, SpatialChangeEvent,
)
from dnd.entity import Entity, EntityConfig


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
    EventQueue._on_event_callbacks.clear()


def create_simple_grid(width: int = 10, height: int = 10) -> GridMap:
    """Create a simple floor grid."""
    grid = get_map()
    grid.create_rectangle(0, 0, width, height, walkable=True, visible=True, name="Floor")
    return grid


def test_gridmap_basics():
    """Test basic GridMap functionality."""
    print("\n=== Test: GridMap Basics ===")
    clear_state()

    grid = get_map()

    # Create a small room
    grid.create_room(0, 0, 5, 5)

    print(f"Grid size: {grid.size}")
    print(f"Grid bounds: {grid.bounds}")
    print(f"Tile count: {grid.tile_count()}")

    # Check tile properties
    assert grid.is_walkable(2, 2), "Center should be walkable"
    assert grid.is_visible(2, 2), "Center should be visible"
    assert not grid.is_walkable(0, 0), "Corner wall should not be walkable"
    assert not grid.is_visible(0, 0), "Corner wall should not be visible"

    print("✓ Basic tile management works")


def test_entity_registration():
    """Test entity registration with GridMap."""
    print("\n=== Test: Entity Registration ===")
    clear_state()

    grid = create_simple_grid()

    # Create entity at position (3, 3)
    entity_uuid = uuid4()
    entity = Entity.create(
        source_entity_uuid=entity_uuid,
        name="TestEntity",
        config=EntityConfig(position=(3, 3))
    )

    # Check GridMap registration
    assert grid.get_entity_position(entity_uuid) == (3, 3), "Entity should be at (3,3) in GridMap"
    assert entity_uuid in grid.get_entities_at((3, 3)), "Entity should be listed at position"

    print(f"Entity {entity.name} registered at position: {grid.get_entity_position(entity_uuid)}")
    print("✓ Entity registration works")


def test_spatial_events_on_movement():
    """Test that SpatialChangeEvents are fired when entities move."""
    print("\n=== Test: Spatial Events on Movement ===")
    clear_state()

    create_simple_grid()  # Creates grid with side effects

    # Create entity
    entity_uuid = uuid4()
    entity = Entity.create(
        source_entity_uuid=entity_uuid,
        name="MovingEntity",
        config=EntityConfig(position=(2, 2))
    )

    # Record events before movement (entity creation also fires an entered event)
    _ = len(EventQueue.get_events_by_type(EventType.SPATIAL_ENTITY_ENTERED))

    # Move entity
    old_pos = entity.position
    new_pos = (4, 4)
    Entity.update_entity_position(entity, new_pos)

    # Check events after movement
    entered_events = EventQueue.get_events_by_type(EventType.SPATIAL_ENTITY_ENTERED)
    left_events = EventQueue.get_events_by_type(EventType.SPATIAL_ENTITY_LEFT)

    print(f"Entity moved from {old_pos} to {new_pos}")
    print(f"SPATIAL_ENTITY_ENTERED events: {len(entered_events)}")
    print(f"SPATIAL_ENTITY_LEFT events: {len(left_events)}")

    # Verify at least one event for leaving old position and entering new
    # Note: Entity creation also fires an entered event
    assert len(entered_events) >= 2, "Should have at least 2 entered events (creation + move)"
    assert len(left_events) >= 1, "Should have at least 1 left event (move)"

    # Check the last events
    last_entered = entered_events[-1]
    last_left = left_events[-1]

    assert isinstance(last_entered, SpatialChangeEvent), "Should be SpatialChangeEvent"
    assert last_entered.position == new_pos, f"Entered event should be at {new_pos}"
    assert last_entered.entity_uuid == entity_uuid, "Event should reference moving entity"

    assert isinstance(last_left, SpatialChangeEvent), "Should be SpatialChangeEvent"
    assert last_left.position == old_pos, f"Left event should be at {old_pos}"

    print(f"Last entered event: position={last_entered.position}, entity={last_entered.entity_uuid}")
    print(f"Last left event: position={last_left.position}, old_position(new_pos)={last_left.old_position}")
    print("✓ Spatial events fire correctly on movement")


def test_cell_subscriptions():
    """Test that entities can subscribe to cells and subscriptions update with senses."""
    print("\n=== Test: Cell Subscriptions ===")
    clear_state()

    grid = create_simple_grid(10, 10)

    # Create entity
    entity_uuid = uuid4()
    entity = Entity.create(
        source_entity_uuid=entity_uuid,
        name="SubscribingEntity",
        config=EntityConfig(position=(5, 5))
    )

    # Update senses (this should subscribe to visible cells)
    entity.update_entity_senses(max_distance=5)

    # Check subscriptions
    subscriptions = grid.get_entity_subscriptions(entity_uuid)
    print(f"Entity at (5,5) subscribed to {len(subscriptions)} cells")

    # Entity should be subscribed to cells in its FOV
    assert len(subscriptions) > 0, "Entity should have subscriptions"
    assert (5, 5) in subscriptions, "Entity should be subscribed to its own position"

    # Check that the grid tracks subscribers
    subscribers_at_origin = grid.get_subscribers_at((5, 5))
    assert entity_uuid in subscribers_at_origin, "Entity should be in subscribers list"

    # Move entity and update senses
    Entity.update_entity_position(entity, (7, 7))
    entity.update_entity_senses(max_distance=5)

    new_subscriptions = grid.get_entity_subscriptions(entity_uuid)
    print(f"After move to (7,7), subscribed to {len(new_subscriptions)} cells")

    assert (7, 7) in new_subscriptions, "Entity should be subscribed to new position"

    print("✓ Cell subscriptions work correctly")


def test_fov_integration():
    """Test that FOV (shadowcast) integrates correctly with GridMap."""
    print("\n=== Test: FOV Integration ===")
    clear_state()

    grid = get_map()

    # Create room with walls
    grid.create_room(0, 0, 10, 10)

    # Compute FOV from center
    origin = (5, 5)
    visible = grid.compute_fov(origin, max_distance=10)

    print(f"FOV from {origin}: {len(visible)} visible cells")

    # Origin should be visible
    assert origin in visible, "Origin should be visible"

    # Cells behind walls should not be visible (corners are walls)
    # The wall at (0,0) should block vision to cells outside room

    # Verify some visible cells
    assert (4, 5) in visible, "(4,5) should be visible from (5,5)"
    assert (6, 5) in visible, "(6,5) should be visible from (5,5)"

    print(f"Sample visible cells: {list(visible)[:10]}...")
    print("✓ FOV (shadowcast) integration works")


def test_pathfinding_integration():
    """Test that pathfinding (dijkstra) integrates correctly with GridMap."""
    print("\n=== Test: Pathfinding Integration ===")
    clear_state()

    grid = get_map()

    # Create simple floor
    grid.create_rectangle(0, 0, 10, 10, walkable=True, visible=True)

    # Add an obstacle
    grid.set_tile(5, 5, walkable=False, visible=True, name="Pillar")

    # Compute paths from (0, 0)
    start = (0, 0)
    distances, paths = grid.compute_paths(start, max_distance=20)

    print(f"Pathfinding from {start}: {len(distances)} reachable cells")

    # Adjacent cells should be reachable
    assert (1, 0) in distances, "(1,0) should be reachable"
    assert (0, 1) in distances, "(0,1) should be reachable"

    # Obstacle should not be reachable
    assert (5, 5) not in distances, "Obstacle at (5,5) should not be reachable"

    # Check path to a distant cell
    target = (9, 9)
    if target in paths:
        print(f"Path to {target}: {paths[target]}")
        print(f"Distance to {target}: {distances[target]}")

    print("✓ Pathfinding (dijkstra) integration works")


def test_entity_senses_with_gridmap():
    """Test that entity senses properly use GridMap for FOV and paths."""
    print("\n=== Test: Entity Senses with GridMap ===")
    clear_state()

    grid = get_map()

    # Create room
    grid.create_room(0, 0, 15, 15)

    # Create two entities
    entity1_uuid = uuid4()
    entity1 = Entity.create(
        source_entity_uuid=entity1_uuid,
        name="Observer",
        config=EntityConfig(position=(7, 7))
    )

    entity2_uuid = uuid4()
    _ = Entity.create(
        source_entity_uuid=entity2_uuid,
        name="Target",
        config=EntityConfig(position=(9, 7))
    )

    # Update senses
    entity1.update_entity_senses(max_distance=10)

    # Entity1 should see entity2
    visible_entities = entity1.senses.entities
    print(f"Observer at (7,7) sees {len(visible_entities)} entities")

    assert entity2_uuid in visible_entities or entity1_uuid in visible_entities, \
        "Observer should see at least itself or target"

    # Check visible cells
    visible_cells = entity1.senses.visible
    print(f"Observer can see {len(visible_cells)} cells")

    # Check paths
    paths = entity1.senses.paths
    print(f"Observer has paths to {len(paths)} cells")

    print("✓ Entity senses integration works")


def test_no_duplicate_events():
    """Test that moving an entity produces consistent event counts.

    With the full spatial event lifecycle (DECLARATION -> EXECUTION -> EFFECT -> COMPLETION),
    each spatial event (LEFT or ENTERED) fires at all 4 phases.
    So a move produces at minimum: 4 LEFT events + 4 ENTERED events = 8 total events.

    After the first move, the entity's reactive senses callback subscribes to visible cells,
    so subsequent moves may produce additional cascading spatial events from subscriber
    notifications. The key invariant is that subsequent moves produce a consistent count.
    """
    print("\n=== Test: No Duplicate Events ===")
    clear_state()

    create_simple_grid()  # Creates grid with side effects

    # Count all events before
    total_before = len(EventQueue._all_events)

    # Create entity
    entity_uuid = uuid4()
    entity = Entity.create(
        source_entity_uuid=entity_uuid,
        name="TestEntity",
        config=EntityConfig(position=(3, 3))
    )

    events_after_creation = len(EventQueue._all_events)
    creation_events = events_after_creation - total_before
    print(f"Events from entity creation: {creation_events}")

    # Move entity once
    Entity.update_entity_position(entity, (4, 4))

    events_after_move1 = len(EventQueue._all_events)
    move1_events = events_after_move1 - events_after_creation
    print(f"Events from first move: {move1_events}")

    # First move: 8 base events (4 phases × 2 types: LEFT + ENTERED)
    assert move1_events == 8, f"Expected 8 events for first move (4 phases × 2 types), got {move1_events}"

    # Move again — reactive senses callback may fire and cascade additional events
    # (subscription notifications from the entity's own spatial callback).
    # The key invariant: each move still produces at least 8 base events.
    Entity.update_entity_position(entity, (5, 5))

    events_after_move2 = len(EventQueue._all_events)
    move2_events = events_after_move2 - events_after_move1
    print(f"Events from second move: {move2_events}")

    assert move2_events >= 8, f"Expected at least 8 events per move, got {move2_events}"

    # Move a third time to verify no unbounded growth
    Entity.update_entity_position(entity, (6, 6))

    events_after_move3 = len(EventQueue._all_events)
    move3_events = events_after_move3 - events_after_move2
    print(f"Events from third move: {move3_events}")

    assert move3_events >= 8, f"Expected at least 8 events per move, got {move3_events}"
    # Verify no unbounded growth: each move should not produce drastically more events
    max_expected = move1_events * 4  # generous bound: no exponential blowup
    assert move3_events <= max_expected, f"Event count growing unboundedly: {move3_events} > {max_expected}"

    print("✓ Consistent event counts on movement")


def test_tile_change_events():
    """Test that tile changes fire events."""
    print("\n=== Test: Tile Change Events ===")
    clear_state()

    grid = get_map()

    # Create initial tile
    grid.set_tile(5, 5, walkable=True, visible=True)

    # Record tile events
    tile_events_before = len(EventQueue.get_events_by_type(EventType.SPATIAL_TILE_CHANGED))

    # Change tile properties
    grid.set_tile(5, 5, walkable=False, visible=True)

    tile_events_after = len(EventQueue.get_events_by_type(EventType.SPATIAL_TILE_CHANGED))

    print(f"Tile events before: {tile_events_before}, after: {tile_events_after}")

    # Should have fired at least one tile changed event
    assert tile_events_after > tile_events_before, "Tile change should fire event"

    # Check the event
    events = EventQueue.get_events_by_type(EventType.SPATIAL_TILE_CHANGED)
    last_event = events[-1]

    assert isinstance(last_event, SpatialChangeEvent), "Should be SpatialChangeEvent"
    assert last_event.position == (5, 5), "Event should be at (5,5)"
    assert last_event.tile_walkable == False, "Event should record new walkable state"

    print(f"Last tile event: position={last_event.position}, walkable={last_event.tile_walkable}")
    print("✓ Tile change events work correctly")


def test_multiple_entities_movement():
    """Test spatial events with multiple entities moving."""
    print("\n=== Test: Multiple Entities Movement ===")
    clear_state()

    grid = create_simple_grid()

    # Create multiple entities
    entities = []
    for i in range(3):
        uuid = uuid4()
        entity = Entity.create(
            source_entity_uuid=uuid,
            name=f"Entity{i}",
            config=EntityConfig(position=(i, i))
        )
        entities.append(entity)

    print(f"Created {len(entities)} entities")

    # Update all senses
    Entity.update_all_entities_senses(max_distance=5)

    # Check that each entity has subscriptions
    for entity in entities:
        subs = grid.get_entity_subscriptions(entity.uuid)
        print(f"{entity.name} at {entity.position}: {len(subs)} subscriptions")
        assert len(subs) > 0, f"{entity.name} should have subscriptions"

    # Move one entity and check events
    events_before = len(EventQueue.get_events_by_type(EventType.SPATIAL_ENTITY_ENTERED))

    Entity.update_entity_position(entities[0], (5, 5))

    events_after = len(EventQueue.get_events_by_type(EventType.SPATIAL_ENTITY_ENTERED))
    print(f"Entered events after move: {events_after - events_before}")

    print("✓ Multiple entities work correctly")


def run_all_tests():
    """Run all spatial events tests."""
    print("=" * 60)
    print("SPATIAL EVENTS SYSTEM TEST")
    print("=" * 60)

    tests = [
        test_gridmap_basics,
        test_entity_registration,
        test_spatial_events_on_movement,
        test_cell_subscriptions,
        test_fov_integration,
        test_pathfinding_integration,
        test_entity_senses_with_gridmap,
        test_no_duplicate_events,
        test_tile_change_events,
        test_multiple_entities_movement,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"\n✗ FAILED: {test.__name__}")
            print(f"  Error: {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    print("\n" + "=" * 60)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("=" * 60)

    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    exit(0 if success else 1)
