"""
Test difficult terrain and movement cost system.

Tests:
1. Normal floor tiles have walking_cost = 1
2. Difficult terrain tiles have walking_cost = 2
3. Wall tiles have walking_cost = 0 (impassable)
4. Pathfinding accounts for terrain costs
5. Tile borders block directional movement
"""

from dnd.core.gridmap import get_map, reset_map
from dnd.core.base_tiles import (
    floor_factory, wall_factory, water_factory,
    difficult_terrain_factory,
)
from dnd.core.base_block import MovementMode


def test_tile_movement_costs():
    """Test that different tile types have correct movement costs."""
    print("=" * 60)
    print("TEST: Tile Movement Costs")
    print("=" * 60)

    reset_map()

    # Create different tile types
    floor = floor_factory((0, 0))
    wall = wall_factory((1, 0))
    water = water_factory((2, 0))
    difficult = difficult_terrain_factory((3, 0))

    # Check walking costs
    print(f"\nFloor walking cost: {floor.get_movement_cost(MovementMode.WALKING)}")
    assert floor.get_movement_cost(MovementMode.WALKING) == 1, "Floor should have walking cost 1"

    print(f"Wall walking cost: {wall.get_movement_cost(MovementMode.WALKING)}")
    assert wall.get_movement_cost(MovementMode.WALKING) == 0, "Wall should have walking cost 0 (impassable)"

    print(f"Water walking cost: {water.get_movement_cost(MovementMode.WALKING)}")
    assert water.get_movement_cost(MovementMode.WALKING) == 0, "Water should have walking cost 0 (can't walk)"

    print(f"Difficult terrain walking cost: {difficult.get_movement_cost(MovementMode.WALKING)}")
    assert difficult.get_movement_cost(MovementMode.WALKING) == 2, "Difficult terrain should have walking cost 2"

    # Check swimming costs
    print(f"\nFloor swimming cost: {floor.get_movement_cost(MovementMode.SWIMMING)}")
    assert floor.get_movement_cost(MovementMode.SWIMMING) == 0, "Floor should have swimming cost 0 (no water)"

    print(f"Water swimming cost: {water.get_movement_cost(MovementMode.SWIMMING)}")
    assert water.get_movement_cost(MovementMode.SWIMMING) == 1, "Water should have swimming cost 1"

    # Check flying costs
    print(f"\nFloor flying cost: {floor.get_movement_cost(MovementMode.FLYING)}")
    assert floor.get_movement_cost(MovementMode.FLYING) == 1, "Floor should have flying cost 1"

    print(f"Wall flying cost: {wall.get_movement_cost(MovementMode.FLYING)}")
    assert wall.get_movement_cost(MovementMode.FLYING) == 0, "Wall should have flying cost 0 (solid)"

    print("\n[PASS] All tile movement costs correct!")


def test_pathfinding_with_terrain_costs():
    """Test that pathfinding accounts for terrain costs."""
    print("\n" + "=" * 60)
    print("TEST: Pathfinding with Terrain Costs")
    print("=" * 60)

    reset_map()
    grid = get_map()

    # Create a simple map:
    # [S][.][D][.][E]
    # S = start, E = end, D = difficult terrain, . = floor

    grid.set_tile(0, 0, walkable=True, name="Floor")  # Start
    grid.set_tile(1, 0, walkable=True, name="Floor")
    grid.set_tile(2, 0, walkable=True, name="Floor")  # Will be difficult
    grid.set_tile(3, 0, walkable=True, name="Floor")
    grid.set_tile(4, 0, walkable=True, name="Floor")  # End

    # Make tile (2,0) difficult terrain by adding +1 cost
    tile = grid.get_tile(2, 0)
    if tile:
        from dnd.core.modifiers import NumericalModifier
        tile.walking_cost.self_static.add_value_modifier(
            NumericalModifier.create(
                source_entity_uuid=tile.uuid,
                name="Difficult Terrain",
                value=1
            )
        )
        print(f"Tile (2,0) walking cost after modifier: {tile.get_movement_cost(MovementMode.WALKING)}")

    # Compute paths from start
    distances, _ = grid.compute_paths((0, 0), movement_mode=MovementMode.WALKING)

    print(f"\nDistances from (0,0):")
    for pos in sorted(distances.keys()):
        print(f"  {pos}: {distances[pos]} movement cost")

    # Verify costs
    # (0,0) -> (1,0) = 1 (floor)
    # (1,0) -> (2,0) = 2 (difficult terrain, cost 2)
    # (2,0) -> (3,0) = 1 (floor)
    # (3,0) -> (4,0) = 1 (floor)
    # Total to (4,0) = 1 + 2 + 1 + 1 = 5

    assert distances.get((1, 0)) == 1, f"Distance to (1,0) should be 1, got {distances.get((1, 0))}"
    assert distances.get((2, 0)) == 3, f"Distance to (2,0) should be 3 (1+2), got {distances.get((2, 0))}"
    assert distances.get((3, 0)) == 4, f"Distance to (3,0) should be 4 (1+2+1), got {distances.get((3, 0))}"
    assert distances.get((4, 0)) == 5, f"Distance to (4,0) should be 5 (1+2+1+1), got {distances.get((4, 0))}"

    print("\n[PASS] Pathfinding correctly accounts for terrain costs!")


def test_tile_borders():
    """Test that tile borders block directional movement."""
    print("\n" + "=" * 60)
    print("TEST: Tile Borders")
    print("=" * 60)

    reset_map()
    grid = get_map()

    # Create a 3x1 corridor with a one-way tile in the middle
    grid.set_tile(0, 0, walkable=True, name="Floor")
    grid.set_tile(1, 0, walkable=True, name="Floor")
    grid.set_tile(2, 0, walkable=True, name="Floor")

    # Make tile (1,0) only enterable from the west (can't enter from east)
    middle_tile = grid.get_tile(1, 0)
    assert middle_tile is not None, "Middle tile should exist"

    middle_tile.border_east = False  # Block entry from east (coming from x=2)
    print(f"Middle tile (1,0) borders: N={middle_tile.border_north}, S={middle_tile.border_south}, E={middle_tile.border_east}, W={middle_tile.border_west}")

    # Test can_enter_from
    print(f"\nCan enter (1,0) from (0,0) [west]: {middle_tile.can_enter_from((0, 0))}")
    assert middle_tile.can_enter_from((0, 0)) == True, "Should be able to enter from west"

    print(f"Can enter (1,0) from (2,0) [east]: {middle_tile.can_enter_from((2, 0))}")
    assert middle_tile.can_enter_from((2, 0)) == False, "Should NOT be able to enter from east"

    # Test pathfinding respects borders
    # From (0,0), should be able to reach (1,0) and (2,0)
    distances_from_west, _ = grid.compute_paths((0, 0))
    print(f"\nFrom (0,0) - reachable: {sorted(distances_from_west.keys())}")

    # From (2,0), should only be able to reach itself (can't go through middle tile)
    distances_from_east, _ = grid.compute_paths((2, 0))
    print(f"From (2,0) - reachable: {sorted(distances_from_east.keys())}")

    # From west, should reach all tiles
    assert (1, 0) in distances_from_west, "Should reach (1,0) from west"
    assert (2, 0) in distances_from_west, "Should reach (2,0) from west"

    # From east, cannot enter (1,0)
    assert (1, 0) not in distances_from_east, "Should NOT reach (1,0) from east (border blocks)"

    print("\n[PASS] Tile borders correctly block directional movement!")


def test_tile_uuid_lookup():
    """Test that tiles can be looked up by UUID."""
    print("\n" + "=" * 60)
    print("TEST: Tile UUID Lookup")
    print("=" * 60)

    reset_map()
    grid = get_map()

    # Create a tile
    tile = grid.set_tile(5, 5, walkable=True, name="Test Floor")
    print(f"Created tile at (5,5) with UUID: {tile.uuid}")

    # Look it up by UUID
    found_tile = grid.get_tile_by_uuid(tile.uuid)
    assert found_tile is not None, "Should find tile by UUID"
    assert found_tile.position == (5, 5), f"Found tile should be at (5,5), got {found_tile.position}"
    print(f"Found tile by UUID at position: {found_tile.position}")

    # Remove the tile
    grid.remove_tile(5, 5)

    # Should no longer find it
    not_found = grid.get_tile_by_uuid(tile.uuid)
    assert not_found is None, "Should not find removed tile"
    print("Tile correctly not found after removal")

    print("\n[PASS] Tile UUID lookup works correctly!")


def test_move_action_uses_terrain_costs():
    """Test that Move action calculates cost from terrain, not just path length."""
    print("\n" + "=" * 60)
    print("TEST: Move Action Uses Terrain Costs")
    print("=" * 60)

    from dnd.utils import reset_combat_state
    from dnd.monsters.bestiary import create_skeleton
    from dnd.actions import Move
    from dnd.entity import Entity
    from dnd.core.modifiers import NumericalModifier

    reset_combat_state()
    grid = get_map()

    # Create a 5x1 corridor with difficult terrain in the middle
    # [S][.][D][.][E]  where D = difficult terrain (cost 2)
    for x in range(5):
        grid.set_tile(x, 0, walkable=True, name="Floor")

    # Make tile (2,0) difficult terrain
    tile = grid.get_tile(2, 0)
    assert tile is not None
    tile.walking_cost.self_static.add_value_modifier(
        NumericalModifier.create(
            source_entity_uuid=tile.uuid,
            name="Difficult Terrain",
            value=1  # Cost becomes 2
        )
    )

    # Create entity at start with 30ft movement
    entity = create_skeleton(name="Test Entity", position=(0, 0))
    Entity.update_all_entities_senses(max_distance=20)

    print(f"Entity at {entity.position} with {entity.action_economy.movement.normalized_score}ft movement")
    print(f"Tile (2,0) cost: {tile.get_movement_cost(MovementMode.WALKING)}")

    # Create Move action to position (4, 0)
    # Path: (0,0) -> (1,0) -> (2,0) -> (3,0) -> (4,0)
    # Costs: 1 + 2 + 1 + 1 = 5 cost units = 25 feet
    move = Move(
        source_entity_uuid=entity.uuid,
        end_position=(4, 0)
    )

    # Check the computed cost
    movement_cost = None
    for cost in move.costs:
        if cost.cost_type == "movement":
            movement_cost = cost.cost
            break

    print(f"Move action computed cost: {movement_cost}ft")
    print(f"Path: {move.path}")

    # Without terrain: 4 tiles * 5ft = 20ft
    # With terrain: (1+2+1+1) * 5ft = 25ft
    assert movement_cost == 25, f"Expected 25ft cost (terrain-aware), got {movement_cost}ft"

    print("\n[PASS] Move action correctly uses terrain costs!")


def main():
    """Run all terrain tests."""
    print("\n" + "=" * 60)
    print("TERRAIN AND MOVEMENT COST SYSTEM TESTS")
    print("=" * 60)

    test_tile_movement_costs()
    test_pathfinding_with_terrain_costs()
    test_tile_borders()
    test_tile_uuid_lookup()
    test_move_action_uses_terrain_costs()

    print("\n" + "=" * 60)
    print("ALL TESTS PASSED!")
    print("=" * 60)


if __name__ == "__main__":
    main()
