"""Tests for light propagation through blocking changes (doors).

When a door opens, light sources whose illumination was clipped by the door
must recompute. Verifies that recompute_lights_at_position() correctly
expands/contracts light through changed blocking geometry.

Setup: Dark arena with vertical wall at x=7, door at (7,7).
Light sources on one or both sides. Entity observes from the other side.
"""

import sys
from uuid import uuid4

from dnd.utils import reset_combat_state
from dnd.entity import Entity
from dnd.core.base_block import LightLevel
from dnd.core.gridmap import get_map
from dnd.monsters.bestiary import create_skeleton
from dnd.actions_functional import setup_standard_actions
from dnd.items.test_items import TestDoorA, create_wall_torch
from dnd.maps.arena_layout import build_dark_standard_barrier_fixture

passed = 0
failed = 0


def check(description: str, condition: bool):
    global passed, failed
    if condition:
        passed += 1
        print(f"  [PASS] {description}")
    else:
        failed += 1
        print(f"  [FAIL] {description}")


def section(title: str):
    print(f"\n{'='*60}")
    print(f"TEST: {title}")
    print(f"{'='*60}")


def tile_light(x: int, y: int) -> LightLevel:
    grid = get_map()
    t = grid.get_tile(x, y)
    assert t is not None, f"No tile at ({x}, {y})"
    return t.resolved_light_level


def create_dark_arena_with_wall_and_door():
    """Create a dark arena with the standard directional wall and door."""
    reset_combat_state()
    grid = get_map()
    barrier = build_dark_standard_barrier_fixture(grid)
    return grid, barrier.door


# =============================================================================
# Test 1: Door closed — light blocked
# =============================================================================
section("Door closed — light blocked")
grid, door = create_dark_arena_with_wall_and_door()

# Wall torch on the right side at (10,7) — bright 10ft, dim 10ft
wt = create_wall_torch(position=(10, 7), owner_uuid=uuid4(), lit=True)

# Observer on the left side
observer = create_skeleton(name="Observer", position=(5, 7), faction="heroes", darkvision=False)
setup_standard_actions(observer)
Entity.update_all_entities_senses()

# Right side of door should be lit
check("Tile (10,7) is VERY_BRIGHT (torch location)", tile_light(10, 7) == LightLevel.VERY_BRIGHT)
check("Tile (9,7) has light", tile_light(9, 7) != LightLevel.DARKNESS)

# Left side of door should be dark — door blocks light
check("Tile (6,7) is DARKNESS (door blocks light)", tile_light(6, 7) == LightLevel.DARKNESS)
check("Tile (5,7) is DARKNESS (observer position)", tile_light(5, 7) == LightLevel.DARKNESS)

# Door position itself may have light (shadowcast includes blocking cell)
# but left side beyond should be dark
check("Tile (4,7) is DARKNESS", tile_light(4, 7) == LightLevel.DARKNESS)


# =============================================================================
# Test 2: Door opens — light propagates through
# =============================================================================
section("Door opens — light propagates")

# Open the door
door.open()

# Right side should still be lit
check("Tile (10,7) still BRIGHT after open", tile_light(10, 7) == LightLevel.VERY_BRIGHT)

# Tiles between door and torch should still be lit
check("Tile (8,7) has light after open", tile_light(8, 7) != LightLevel.DARKNESS)

# Door position should now have light passing through
check("Tile (7,7) has light after open (door position)", tile_light(7, 7) != LightLevel.DARKNESS)

# Left side should now receive light (depending on torch radius)
# Torch at (10,7): bright 10ft=2tiles, dim 10ft=2tiles, total radius=4 tiles
# (6,7) is 4 tiles from (10,7) — should be within dim range
check("Tile (6,7) has light after open (light propagated)", tile_light(6, 7) != LightLevel.DARKNESS)


# =============================================================================
# Test 3: Door closes — light recedes
# =============================================================================
section("Door closes — light recedes")

door.close()

# Right side still lit
check("Tile (10,7) still BRIGHT after close", tile_light(10, 7) == LightLevel.VERY_BRIGHT)

# Left side should revert to darkness
check("Tile (6,7) reverts to DARKNESS after close", tile_light(6, 7) == LightLevel.DARKNESS)
check("Tile (5,7) reverts to DARKNESS after close", tile_light(5, 7) == LightLevel.DARKNESS)


# =============================================================================
# Test 4: Light source adjacent to door
# =============================================================================
section("Light source adjacent to door")
grid, door = create_dark_arena_with_wall_and_door()

# Light source right next to door on the right at (8,7)
wt_near = create_wall_torch(position=(8, 7), owner_uuid=uuid4(), lit=True)

Entity.update_all_entities_senses()

# Closed: left side dark
check("(6,7) dark with closed door (adjacent light)", tile_light(6, 7) == LightLevel.DARKNESS)

# Open door
door.open()

# Door position should get light
check("(7,7) has light after open (adjacent torch)", tile_light(7, 7) != LightLevel.DARKNESS)

# Tile just past door should get light (if within radius)
# Torch at (8,7) bright 10ft=2tiles: (7,7) is 1 tile away = bright range
check("(7,7) is BRIGHT from adjacent torch", tile_light(7, 7) == LightLevel.VERY_BRIGHT)

# Close again
door.close()

check("(6,7) dark again after close", tile_light(6, 7) == LightLevel.DARKNESS)


# =============================================================================
# Test 5: Multiple light sources on opposite sides
# =============================================================================
section("Multiple light sources on opposite sides")
grid, door = create_dark_arena_with_wall_and_door()

# Light on right side
wt_right = create_wall_torch(position=(10, 7), owner_uuid=uuid4(), lit=True)
# Light on left side
wt_left = create_wall_torch(position=(4, 7), owner_uuid=uuid4(), lit=True)

Entity.update_all_entities_senses()

# With door closed, each side is independently lit
check("(10,7) bright (right torch)", tile_light(10, 7) == LightLevel.VERY_BRIGHT)
check("(4,7) bright (left torch)", tile_light(4, 7) == LightLevel.VERY_BRIGHT)
check("(6,7) has light from left torch (closed door)", tile_light(6, 7) != LightLevel.DARKNESS)
check("(8,7) has light from right torch (closed door)", tile_light(8, 7) != LightLevel.DARKNESS)

# Open door — both torches should recompute and light the corridor
door.open()

check("(7,7) has light after open (both torches)", tile_light(7, 7) != LightLevel.DARKNESS)
# Both sides should still be lit
check("(10,7) still bright after open", tile_light(10, 7) == LightLevel.VERY_BRIGHT)
check("(4,7) still bright after open", tile_light(4, 7) == LightLevel.VERY_BRIGHT)

# Close door — revert
door.close()

check("(10,7) still bright after close", tile_light(10, 7) == LightLevel.VERY_BRIGHT)
check("(4,7) still bright after close", tile_light(4, 7) == LightLevel.VERY_BRIGHT)


# =============================================================================
# Test 6: Object inside lit area changes blocking
# =============================================================================
section("Object inside lit area changes blocking")
reset_combat_state()
grid = get_map()
grid.create_rectangle(0, 0, 15, 15)

for _, tile in grid._tiles.items():
    tile.default_light = LightLevel.DARKNESS

# Wall at x=5, y=4..10 with door at (5,7) — BEFORE light source
for y in range(4, 11):
    if y != 7:
        grid.set_tile(5, y, walkable=False, visible=False, name="Wall")
door2 = TestDoorA(source_entity_uuid=uuid4())
grid.place_object(door2.uuid, (5, 7))

# Light source at (2,7) — bright 10ft=2tiles, dim 10ft=2tiles
wt_src = create_wall_torch(position=(2, 7), owner_uuid=uuid4(), lit=True)

Entity.update_all_entities_senses()

# With wall+door closed, light from (2,7) can't reach (6,7)
check("(3,7) has light (before wall)", tile_light(3, 7) != LightLevel.DARKNESS)
check("(6,7) dark (blocked by wall+door)", tile_light(6, 7) == LightLevel.DARKNESS)

# Open the door
old_bm = door2.blocks_movement
old_bv = door2.blocks_vision_field
door2.is_open = True
door2.blocks_movement = False
door2.blocks_vision_field = False
door2._notify_blocking_changed(old_bm, old_bv)

# Light should now pass through (5,7) — (6,7) is 4 tiles from (2,7) = dim range
check("(5,7) has light after open (door position)", tile_light(5, 7) != LightLevel.DARKNESS)
check("(6,7) has light after open (past wall)", tile_light(6, 7) != LightLevel.DARKNESS)

# Close door — light recedes
old_bm = door2.blocks_movement
old_bv = door2.blocks_vision_field
door2.is_open = False
door2.blocks_movement = True
door2.blocks_vision_field = True
door2._notify_blocking_changed(old_bm, old_bv)

check("(6,7) dark after close", tile_light(6, 7) == LightLevel.DARKNESS)


# =============================================================================
# Test 7: Senses update — entity sees through opened door with light
# =============================================================================
section("Senses update through door with light")
grid, door = create_dark_arena_with_wall_and_door()

# Torch on the right
wt_senses = create_wall_torch(position=(10, 7), owner_uuid=uuid4(), lit=True)

# Observer on left (no darkvision)
observer = create_skeleton(name="Observer", position=(5, 7), faction="heroes", darkvision=False)
setup_standard_actions(observer)

# Target on right side in lit area
target = create_skeleton(name="Target", position=(9, 7), faction="enemies")

Entity.update_all_entities_senses()

# Door closed: observer can't see target
check("Target NOT visible through closed door", target.uuid not in observer.senses.entities)

# Open door
door.open()

# Senses need full recompute after FOV change — the SPATIAL_OBJECT_CHANGED event
# sets requires_fov which triggers senses update callback
Entity.update_all_entities_senses()

check("Target visible through open door with light", target.uuid in observer.senses.entities)


# =============================================================================
# Test 8: Tile change (wall -> floor) propagates light automatically
# =============================================================================
section("Tile change (wall -> floor) propagates light via callback")
reset_combat_state()
grid = get_map()
grid.create_rectangle(0, 0, 15, 15)

# Make all tiles dark
for _, tile in grid._tiles.items():
    tile.default_light = LightLevel.DARKNESS

# Wall at x=5, y=4..10 (solid wall, no door)
for y in range(4, 11):
    grid.set_tile(5, y, walkable=False, visible=False, name="Wall")

# Light source on left side at (3,7) — bright 10ft=2tiles, dim 10ft=2tiles
wt_tile = create_wall_torch(position=(3, 7), owner_uuid=uuid4(), lit=True)

Entity.update_all_entities_senses()

# Left side lit, right side blocked by wall
check("(3,7) bright (torch position)", tile_light(3, 7) == LightLevel.VERY_BRIGHT)
check("(4,7) has light (before wall)", tile_light(4, 7) != LightLevel.DARKNESS)
check("(6,7) dark (wall blocks light)", tile_light(6, 7) == LightLevel.DARKNESS)

# Replace wall at (5,7) with a floor tile — light should propagate automatically
grid.set_tile(5, 7, walkable=True, visible=True, name="Floor")

# Light should now pass through the opened gap
# (5,7) is 2 tiles from (3,7) = bright range
check("(5,7) has light after wall->floor", tile_light(5, 7) != LightLevel.DARKNESS)
# (6,7) is 3 tiles from (3,7) = dim range
check("(6,7) has light after wall->floor (propagated through gap)", tile_light(6, 7) != LightLevel.DARKNESS)
# (7,7) is 4 tiles from (3,7) = still within total radius (4 tiles)
check("(7,7) has light after wall->floor (dim range)", tile_light(7, 7) != LightLevel.DARKNESS)

# Now put the wall back — light should recede
grid.set_tile(5, 7, walkable=False, visible=False, name="Wall")

check("(6,7) dark after floor->wall", tile_light(6, 7) == LightLevel.DARKNESS)
check("(7,7) dark after floor->wall", tile_light(7, 7) == LightLevel.DARKNESS)
# Left side should still be lit
check("(3,7) still bright after floor->wall", tile_light(3, 7) == LightLevel.VERY_BRIGHT)



# =============================================================================
# Test 9: remove_tile + set_tile (wall destruction → floor) propagates light
# =============================================================================
section("remove_tile + set_tile (wall destruction) propagates light")
reset_combat_state()
grid = get_map()
grid.create_rectangle(0, 0, 15, 15)

for _, tile in grid._tiles.items():
    tile.default_light = LightLevel.DARKNESS

# Wall at x=5, y=4..10
for y in range(4, 11):
    grid.set_tile(5, y, walkable=False, visible=False, name="Wall")

# Torch at (3,7) — bright 10ft=2tiles, dim 10ft=2tiles
wt_remove = create_wall_torch(position=(3, 7), owner_uuid=uuid4(), lit=True)

Entity.update_all_entities_senses()

# Wall blocks light to the right side
check("(6,7) dark (wall blocks)", tile_light(6, 7) == LightLevel.DARKNESS)

# Simulate wall destruction: remove_tile then set_tile with floor
# This is the realistic pattern: wall is destroyed, floor appears
grid.remove_tile(5, 7)
grid.set_tile(5, 7, walkable=True, visible=True, name="Floor")

# Light should now propagate through the gap
check("(5,7) has light after wall destroyed", tile_light(5, 7) != LightLevel.DARKNESS)
check("(6,7) has light after wall destroyed (propagated)", tile_light(6, 7) != LightLevel.DARKNESS)

# Tiles that were lit before should still be lit
check("(4,7) still has light", tile_light(4, 7) != LightLevel.DARKNESS)
check("(3,7) still bright", tile_light(3, 7) == LightLevel.VERY_BRIGHT)


# =============================================================================
# Summary
# =============================================================================
print(f"\n{'='*60}")
print(f"RESULTS: {passed} passed, {failed} failed, {passed + failed} total")
print(f"{'='*60}")

if failed > 0:
    print("SOME TESTS FAILED!")
    sys.exit(1)
else:
    print("ALL TESTS PASSED!")
    sys.exit(0)
