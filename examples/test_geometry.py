"""Test geometry primitives independent of game state."""
from dnd.core.geometry import (
    circle_positions,
    bresenham_line,
    line_positions,
    cone_positions,
    rectangle_positions
)


def test_circle_radius_2():
    """Test circle with radius 2."""
    print("\n=== Circle Radius 2 ===")
    pos = circle_positions((5, 5), 2)

    # Center should be included
    assert (5, 5) in pos, "Center should be included"

    # Cardinals at distance 2 should be included
    assert (7, 5) in pos, "East at distance 2 should be included"
    assert (3, 5) in pos, "West at distance 2 should be included"
    assert (5, 7) in pos, "North at distance 2 should be included"
    assert (5, 3) in pos, "South at distance 2 should be included"

    # Diagonals at distance sqrt(2) ≈ 1.41 should be included
    assert (4, 4) in pos, "SW diagonal should be included"
    assert (4, 6) in pos, "NW diagonal should be included"
    assert (6, 4) in pos, "SE diagonal should be included"
    assert (6, 6) in pos, "NE diagonal should be included"

    # Corners at distance sqrt(8) ≈ 2.83 should be EXCLUDED
    assert (3, 3) not in pos, "Far SW corner should be excluded"
    assert (3, 7) not in pos, "Far NW corner should be excluded"
    assert (7, 3) not in pos, "Far SE corner should be excluded"
    assert (7, 7) not in pos, "Far NE corner should be excluded"

    print(f"Circle positions: {len(pos)} tiles")
    print_circle(pos, (5, 5), 2)
    print("✓ Circle radius 2 passed")


def test_circle_exclude_center():
    """Test circle with center excluded."""
    print("\n=== Circle Exclude Center ===")
    pos = circle_positions((5, 5), 2, include_center=False)
    assert (5, 5) not in pos, "Center should be excluded when include_center=False"
    print("✓ Circle exclude center passed")


def test_bresenham_straight():
    """Test Bresenham line - straight horizontal."""
    print("\n=== Bresenham Straight Line ===")
    line = bresenham_line((0, 0), (5, 0))
    expected = [(0, 0), (1, 0), (2, 0), (3, 0), (4, 0), (5, 0)]
    assert line == expected, f"Expected {expected}, got {line}"
    print(f"Line: {line}")
    print("✓ Bresenham straight passed")


def test_bresenham_vertical():
    """Test Bresenham line - straight vertical."""
    print("\n=== Bresenham Vertical Line ===")
    line = bresenham_line((0, 0), (0, 4))
    expected = [(0, 0), (0, 1), (0, 2), (0, 3), (0, 4)]
    assert line == expected, f"Expected {expected}, got {line}"
    print(f"Line: {line}")
    print("✓ Bresenham vertical passed")


def test_bresenham_diagonal():
    """Test Bresenham line - diagonal."""
    print("\n=== Bresenham Diagonal Line ===")
    line = bresenham_line((0, 0), (3, 3))
    # Diagonal should step both x and y
    assert (0, 0) in line
    assert (3, 3) in line
    assert len(line) == 4, f"Expected 4 points, got {len(line)}: {line}"
    print(f"Line: {line}")
    print("✓ Bresenham diagonal passed")


def test_bresenham_steep():
    """Test Bresenham line - steep angle."""
    print("\n=== Bresenham Steep Line ===")
    line = bresenham_line((0, 0), (2, 5))
    assert (0, 0) in line
    assert (2, 5) in line
    print(f"Line: {line}")
    print("✓ Bresenham steep passed")


def test_line_width_1():
    """Test line with width 1."""
    print("\n=== Line Width 1 ===")
    pos = line_positions((0, 0), (5, 0), length=5, width=1)
    # Should be just the centerline
    assert (0, 0) in pos
    assert (5, 0) in pos
    # No width expansion
    assert (0, 1) not in pos
    assert (0, -1) not in pos
    print(f"Line positions: {pos}")
    print("✓ Line width 1 passed")


def test_line_width_3():
    """Test line with width 3."""
    print("\n=== Line Width 3 ===")
    pos = line_positions((0, 0), (5, 0), length=3, width=3)
    # Center line
    assert (0, 0) in pos
    assert (1, 0) in pos
    assert (2, 0) in pos
    assert (3, 0) in pos
    # Width expansion above
    assert (0, 1) in pos
    assert (1, 1) in pos
    # Width expansion below
    assert (0, -1) in pos
    assert (1, -1) in pos
    print(f"Line positions: {len(pos)} tiles")
    print_line(pos, (0, 0), 8, 5)
    print("✓ Line width 3 passed")


def test_cone_east():
    """Test cone pointing east."""
    print("\n=== Cone East ===")
    pos = cone_positions((0, 0), (5, 0), length=3, angle_degrees=53)

    # Tiles in front should be included
    assert (1, 0) in pos, "Tile at (1,0) should be in cone"
    assert (2, 0) in pos, "Tile at (2,0) should be in cone"
    assert (3, 0) in pos, "Tile at (3,0) should be in cone"

    # Tiles behind should be excluded
    assert (-1, 0) not in pos, "Tile behind cone should be excluded"

    # Apex is not included
    assert (0, 0) not in pos, "Apex should not be included"

    print(f"Cone positions: {len(pos)} tiles")
    print_cone(pos, (0, 0), 6)
    print("✓ Cone east passed")


def test_cone_north():
    """Test cone pointing north."""
    print("\n=== Cone North ===")
    pos = cone_positions((0, 0), (0, 5), length=3, angle_degrees=53)

    # Tiles in front (north) should be included
    assert (0, 1) in pos, "Tile at (0,1) should be in cone"
    assert (0, 2) in pos, "Tile at (0,2) should be in cone"
    assert (0, 3) in pos, "Tile at (0,3) should be in cone"

    # Tiles behind should be excluded
    assert (0, -1) not in pos, "Tile behind cone should be excluded"

    print(f"Cone positions: {len(pos)} tiles")
    print_cone_offset(pos, (0, 0), (-2, -1), 5, 6)
    print("✓ Cone north passed")


def test_cone_diagonal():
    """Test cone pointing northeast."""
    print("\n=== Cone Diagonal (NE) ===")
    pos = cone_positions((0, 0), (5, 5), length=3, angle_degrees=53)

    # Diagonal tiles should be included
    assert (1, 1) in pos, "Tile at (1,1) should be in cone"
    assert (2, 2) in pos, "Tile at (2,2) should be in cone"

    # Behind should be excluded
    assert (-1, -1) not in pos

    print(f"Cone positions: {len(pos)} tiles")
    print_cone_offset(pos, (0, 0), (-1, -1), 6, 6)
    print("✓ Cone diagonal passed")


def test_rectangle_centered():
    """Test centered rectangle."""
    print("\n=== Rectangle Centered 3x3 ===")
    pos = rectangle_positions((5, 5), size=3, centered=True)

    assert len(pos) == 9, f"Expected 9 tiles for 3x3, got {len(pos)}"

    # All tiles in 3x3 centered on (5,5)
    for dx in range(-1, 2):
        for dy in range(-1, 2):
            assert (5 + dx, 5 + dy) in pos, f"({5+dx}, {5+dy}) should be in rectangle"

    print(f"Rectangle positions: {pos}")
    print("✓ Rectangle centered passed")


def test_rectangle_non_centered_east():
    """Test non-centered rectangle extending east."""
    print("\n=== Rectangle Non-Centered East ===")
    pos = rectangle_positions((0, 0), size=3, direction=(5, 0), centered=False)

    # Should extend east from origin, with width
    assert (0, 0) in pos
    assert (1, 0) in pos
    assert (2, 0) in pos
    # Width above and below
    assert (0, 1) in pos
    assert (0, -1) in pos

    print(f"Rectangle positions: {len(pos)} tiles")
    print_rect(pos, (0, 0), 5, 5)
    print("✓ Rectangle non-centered east passed")


def test_rectangle_non_centered_north():
    """Test non-centered rectangle extending north."""
    print("\n=== Rectangle Non-Centered North ===")
    pos = rectangle_positions((0, 0), size=3, direction=(0, 5), centered=False)

    # Should extend north from origin, with width
    assert (0, 0) in pos
    assert (0, 1) in pos
    assert (0, 2) in pos
    # Width left and right
    assert (-1, 0) in pos
    assert (1, 0) in pos

    print(f"Rectangle positions: {len(pos)} tiles")
    print_rect_offset(pos, (0, 0), (-2, -1), 5, 5)
    print("✓ Rectangle non-centered north passed")


# === Visualization Helpers ===

def print_circle(positions, center, radius):
    """ASCII visualization for circle."""
    cx, cy = center
    for y in range(cy + radius + 1, cy - radius - 2, -1):
        row = ""
        for x in range(cx - radius - 1, cx + radius + 2):
            if (x, y) == center:
                row += "O"
            elif (x, y) in positions:
                row += "X"
            else:
                row += "."
        print(f"  {row}")


def print_line(positions, origin, width, height):
    """ASCII visualization for line."""
    _ox, _oy = origin  # Unused but kept for consistency
    for y in range(height - 1, -height, -1):
        row = ""
        for x in range(0, width):
            if (x, y) == origin:
                row += "O"
            elif (x, y) in positions:
                row += "X"
            else:
                row += "."
        print(f"  {row}")


def print_cone(positions, apex, size):
    """ASCII visualization for cone."""
    _ax, _ay = apex  # Unused but kept for consistency
    for y in range(size - 1, -size, -1):
        row = ""
        for x in range(-1, size):
            if (x, y) == apex:
                row += "O"
            elif (x, y) in positions:
                row += "X"
            else:
                row += "."
        print(f"  {row}")


def print_cone_offset(positions, apex, offset, width, height):
    """ASCII visualization for cone with offset."""
    _ax, _ay = apex  # Unused but kept for consistency
    ofx, ofy = offset
    for y in range(ofy + height - 1, ofy - 1, -1):
        row = ""
        for x in range(ofx, ofx + width):
            if (x, y) == apex:
                row += "O"
            elif (x, y) in positions:
                row += "X"
            else:
                row += "."
        print(f"  {row}")


def print_rect(positions, origin, width, height):
    """ASCII visualization for rectangle."""
    _ox, _oy = origin  # Unused but kept for consistency
    for y in range(height - 1, -height, -1):
        row = ""
        for x in range(0, width):
            if (x, y) == origin:
                row += "O"
            elif (x, y) in positions:
                row += "X"
            else:
                row += "."
        print(f"  {row}")


def print_rect_offset(positions, origin, offset, width, height):
    """ASCII visualization for rectangle with offset."""
    _ox, _oy = origin  # Unused but kept for consistency
    ofx, ofy = offset
    for y in range(ofy + height - 1, ofy - 1, -1):
        row = ""
        for x in range(ofx, ofx + width):
            if (x, y) == origin:
                row += "O"
            elif (x, y) in positions:
                row += "X"
            else:
                row += "."
        print(f"  {row}")


if __name__ == "__main__":
    # Circle tests
    test_circle_radius_2()
    test_circle_exclude_center()

    # Bresenham tests
    test_bresenham_straight()
    test_bresenham_vertical()
    test_bresenham_diagonal()
    test_bresenham_steep()

    # Line tests
    test_line_width_1()
    test_line_width_3()

    # Cone tests
    test_cone_east()
    test_cone_north()
    test_cone_diagonal()

    # Rectangle tests
    test_rectangle_centered()
    test_rectangle_non_centered_east()
    test_rectangle_non_centered_north()

    print("\n" + "=" * 50)
    print("All geometry tests passed!")
