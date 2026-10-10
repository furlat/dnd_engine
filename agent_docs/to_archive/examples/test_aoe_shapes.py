"""Test AoE shapes with walls and entities."""
from uuid import uuid4

from dnd.utils import reset_combat_state
from dnd.core.gridmap import get_map
from dnd.core.aoe import Sphere, Cone, Line, Cube
from dnd.monsters.bestiary import create_skeleton
from dnd.entity import Entity


def test_sphere_basic():
    """Test basic sphere without walls."""
    print("\n=== Sphere Basic ===")
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 15, 15)

    source_uuid = uuid4()
    shape = Sphere(source_entity_uuid=source_uuid, target=(5, 5), radius_feet=10)
    shape.compute_objective(caster_pos=(0, 0))

    # Radius of 10 feet = 2 tiles
    assert (5, 5) in shape.affected_positions, "Center should be affected"
    assert (7, 5) in shape.affected_positions, "2 tiles east should be affected"
    assert (3, 5) in shape.affected_positions, "2 tiles west should be affected"
    # 3 tiles away (15 feet) should NOT be affected
    assert (8, 5) not in shape.affected_positions, "3 tiles away should not be affected"

    print(f"Affected positions: {len(shape.affected_positions)}")
    print_shape(shape, (5, 5), 11, offset=(-5, -5))
    print("✓ Sphere basic passed")


def test_sphere_wall_blocking():
    """Test that walls block sphere effects."""
    print("\n=== Sphere Wall Blocking ===")
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 15, 15)

    # Add a wall between center and east edge
    grid.set_tile(7, 5, walkable=False, visible=False, name="Wall")

    source_uuid = uuid4()
    shape = Sphere(source_entity_uuid=source_uuid, target=(5, 5), radius_feet=20)
    shape.compute_objective(caster_pos=(0, 0))

    # Positions before wall should be affected
    assert (6, 5) in shape.affected_positions, "Position before wall should be affected"

    # The wall itself may or may not be in FOV depending on algorithm
    # Positions behind wall should NOT be affected (no LOS)
    assert (8, 5) not in shape.affected_positions, "Position behind wall should not be affected"
    assert (9, 5) not in shape.affected_positions, "Position 2 tiles behind wall should not be affected"

    print(f"Affected positions: {len(shape.affected_positions)}")
    print_shape_with_walls(shape, (5, 5), grid, 11, offset=(-5, -5))
    print("✓ Sphere wall blocking passed")


def test_sphere_entity_detection():
    """Test that sphere detects entities in affected area."""
    print("\n=== Sphere Entity Detection ===")
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 15, 15)

    # Create entities
    caster = create_skeleton(name="Caster", position=(0, 0))
    target_in = create_skeleton(name="TargetIn", position=(5, 5))
    target_edge = create_skeleton(name="TargetEdge", position=(7, 5))  # 2 tiles from center
    target_out = create_skeleton(name="TargetOut", position=(10, 5))  # 5 tiles from center

    Entity.update_all_entities_senses()

    source_uuid = uuid4()
    shape = Sphere(source_entity_uuid=source_uuid, target=(5, 5), radius_feet=10)
    shape.compute_objective(caster_pos=(0, 0))

    # Target at center should be detected
    assert target_in.uuid in shape.affected_entity_uuids, "Entity at center should be affected"

    # Target at edge (2 tiles = 10 feet) should be detected
    assert target_edge.uuid in shape.affected_entity_uuids, "Entity at radius edge should be affected"

    # Target outside radius should NOT be detected
    assert target_out.uuid not in shape.affected_entity_uuids, "Entity outside radius should not be affected"

    # Caster at (0,0) is outside the sphere centered at (5,5) with radius 2
    assert caster.uuid not in shape.affected_entity_uuids, "Caster outside sphere should not be affected"

    print(f"Affected entities: {len(shape.affected_entity_uuids)}")
    print(f"  - {target_in.name}: IN")
    print(f"  - {target_edge.name}: IN")
    print(f"  - {target_out.name}: OUT")
    print("✓ Sphere entity detection passed")


def test_cone_basic():
    """Test basic cone without walls."""
    print("\n=== Cone Basic ===")
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 15, 15)

    source_uuid = uuid4()
    # Cone from (5,5) pointing east, 15 feet (3 tiles)
    shape = Cone(
        source_entity_uuid=source_uuid,
        target=(10, 5),  # East
        length_feet=15,
        angle_degrees=90  # Wide angle for easier testing
    )
    shape.compute_objective(caster_pos=(5, 5))

    # Tiles in front should be affected
    assert (6, 5) in shape.affected_positions, "Tile directly ahead should be affected"
    assert (7, 5) in shape.affected_positions, "2 tiles ahead should be affected"

    # Tiles behind should NOT be affected
    assert (4, 5) not in shape.affected_positions, "Tile behind should not be affected"

    print(f"Affected positions: {len(shape.affected_positions)}")
    print_shape(shape, (5, 5), 11, offset=(0, 0))
    print("✓ Cone basic passed")


def test_line_basic():
    """Test basic line without walls."""
    print("\n=== Line Basic ===")
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 20, 10)

    source_uuid = uuid4()
    # Line from (0,5) pointing east, 30 feet (6 tiles), 5 feet wide (1 tile)
    shape = Line(
        source_entity_uuid=source_uuid,
        target=(10, 5),  # East
        length_feet=30,
        width_feet=5
    )
    shape.compute_objective(caster_pos=(0, 5))

    # Tiles along line should be affected
    assert (0, 5) in shape.affected_positions, "Origin should be affected"
    assert (3, 5) in shape.affected_positions, "Middle should be affected"
    assert (6, 5) in shape.affected_positions, "End should be affected"

    # Tiles off line should NOT be affected (width = 1)
    assert (3, 7) not in shape.affected_positions, "Off-line tile should not be affected"

    print(f"Affected positions: {len(shape.affected_positions)}")
    print_shape(shape, (0, 5), 10, offset=(0, 0))
    print("✓ Line basic passed")


def test_line_wide():
    """Test line with width > 1."""
    print("\n=== Line Wide ===")
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 20, 10)

    source_uuid = uuid4()
    # Line from (0,5) pointing east, 20 feet (4 tiles), 15 feet wide (3 tiles)
    shape = Line(
        source_entity_uuid=source_uuid,
        target=(10, 5),  # East
        length_feet=20,
        width_feet=15
    )
    shape.compute_objective(caster_pos=(0, 5))

    # Center line should be affected
    assert (0, 5) in shape.affected_positions
    assert (2, 5) in shape.affected_positions

    # Width expansion should be affected
    assert (0, 6) in shape.affected_positions, "Above center should be affected"
    assert (0, 4) in shape.affected_positions, "Below center should be affected"

    print(f"Affected positions: {len(shape.affected_positions)}")
    print_shape(shape, (0, 5), 10, offset=(0, 0))
    print("✓ Line wide passed")


def test_cube_centered():
    """Test centered cube."""
    print("\n=== Cube Centered ===")
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 15, 15)

    source_uuid = uuid4()
    # 15 foot cube (3x3 tiles) centered on (7, 7)
    shape = Cube(
        source_entity_uuid=source_uuid,
        target=(7, 7),
        size_feet=15,
        centered=True
    )
    shape.compute_objective(caster_pos=(0, 0))

    # All 9 tiles in 3x3 should be affected
    assert len(shape.affected_positions) == 9, f"Expected 9 positions, got {len(shape.affected_positions)}"
    assert (7, 7) in shape.affected_positions, "Center should be affected"
    assert (6, 6) in shape.affected_positions, "Corner should be affected"
    assert (8, 8) in shape.affected_positions, "Opposite corner should be affected"

    print(f"Affected positions: {len(shape.affected_positions)}")
    print_shape(shape, (7, 7), 11, offset=(2, 2))
    print("✓ Cube centered passed")


def test_cube_non_centered():
    """Test non-centered cube (extending from caster)."""
    print("\n=== Cube Non-Centered ===")
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 15, 15)

    source_uuid = uuid4()
    # 15 foot cube (3x3 tiles) extending east from (5, 5)
    shape = Cube(
        source_entity_uuid=source_uuid,
        target=(10, 5),  # East direction
        size_feet=15,
        centered=False
    )
    shape.compute_objective(caster_pos=(5, 5))

    # Should extend east from origin
    assert (5, 5) in shape.affected_positions, "Origin should be affected"
    assert (6, 5) in shape.affected_positions, "East of origin should be affected"
    assert (7, 5) in shape.affected_positions, "2 tiles east should be affected"

    # Width expansion
    assert (5, 4) in shape.affected_positions, "Below origin should be affected"
    assert (5, 6) in shape.affected_positions, "Above origin should be affected"

    print(f"Affected positions: {len(shape.affected_positions)}")
    print_shape(shape, (5, 5), 11, offset=(0, 0))
    print("✓ Cube non-centered passed")


def test_wall_blocks_line():
    """Test that walls block line effects."""
    print("\n=== Wall Blocks Line ===")
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 20, 10)

    # Add wall at x=5
    grid.set_tile(5, 5, walkable=False, visible=False, name="Wall")

    source_uuid = uuid4()
    shape = Line(
        source_entity_uuid=source_uuid,
        target=(15, 5),
        length_feet=50,
        width_feet=5
    )
    shape.compute_objective(caster_pos=(0, 5))

    # Positions before wall should be affected
    assert (4, 5) in shape.affected_positions, "Before wall should be affected"

    # Positions after wall should NOT be affected
    assert (6, 5) not in shape.affected_positions, "After wall should not be affected"
    assert (10, 5) not in shape.affected_positions, "Far after wall should not be affected"

    print(f"Affected positions: {len(shape.affected_positions)}")
    print_shape_with_walls(shape, (0, 5), grid, 15, offset=(0, 0))
    print("✓ Wall blocks line passed")


# === Visualization Helpers ===

def print_shape(shape, _origin, size, offset=(0, 0)):
    """ASCII visualization for shape."""
    ox, oy = offset
    print(f"  Origin: {shape.computed_origin}, Target: {shape.target}")
    for y in range(oy + size - 1, oy - 1, -1):
        row = f"{y:2d} "
        for x in range(ox, ox + size):
            if (x, y) == shape.computed_origin:
                row += "O"
            elif (x, y) == shape.target:
                row += "T"
            elif (x, y) in shape.affected_positions:
                row += "X"
            else:
                row += "."
        print(row)


def print_shape_with_walls(shape, _origin, grid, size, offset=(0, 0)):
    """ASCII visualization for shape with walls shown."""
    ox, oy = offset
    print(f"  Origin: {shape.computed_origin}, Target: {shape.target}")
    for y in range(oy + size - 1, oy - 1, -1):
        row = f"{y:2d} "
        for x in range(ox, ox + size):
            tile = grid.get_tile(x, y)
            if (x, y) == shape.computed_origin:
                row += "O"
            elif (x, y) == shape.target:
                row += "T"
            elif tile and not tile.visible:
                row += "#"
            elif (x, y) in shape.affected_positions:
                row += "X"
            else:
                row += "."
        print(row)


if __name__ == "__main__":
    # Sphere tests
    test_sphere_basic()
    test_sphere_wall_blocking()
    test_sphere_entity_detection()

    # Cone tests
    test_cone_basic()

    # Line tests
    test_line_basic()
    test_line_wide()
    test_wall_blocks_line()

    # Cube tests
    test_cube_centered()
    test_cube_non_centered()

    print("\n" + "=" * 50)
    print("All AoE shape tests passed!")
