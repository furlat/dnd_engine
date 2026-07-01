"""Test door interaction: sorcerer moves to door, opens it.

Setup: 15x15 arena with vertical wall at x=7 (gap at y=7 with closed door).
Sorcerer starts at (5,7), moves to (6,7), opens the door.
"""
import sys

from dnd.utils import reset_combat_state, setup_combat_arena, get_position, move_entity
from dnd.core.gridmap import get_map
from dnd.entity import Entity
from dnd.monsters.bestiary import create_caster, create_skeleton
from dnd.maps.arena_layout import create_standard_arena_floor, place_standard_directional_barrier
from dnd.actions_functional import get_available_actions, execute_use_action

passed = 0
failed = 0

def test(name, condition):
    global passed, failed
    if condition:
        print(f"  PASS: {name}")
        passed += 1
    else:
        print(f"  FAIL: {name}")
        failed += 1


def setup():
    """Create arena with wall, door, sorcerer, and skeleton."""
    reset_combat_state()
    grid = get_map()
    create_standard_arena_floor(grid)
    barrier = place_standard_directional_barrier(grid)
    door = barrier.door

    # Sorcerer on the left side, skeleton on the right
    sorcerer = create_caster(name="Sorcerer", position=(5, 7), faction="heroes")
    skeleton = create_skeleton(name="Skeleton", position=(12, 7), faction="monsters")

    Entity.update_all_entities_senses()
    return sorcerer, skeleton, door


print("=" * 60)
print("Test: Door Interaction with Sorcerer")
print("=" * 60)

# --- Setup ---
print("\n--- Setup ---")
sorcerer, skeleton, door = setup()
encounter = setup_combat_arena(sorcerer, skeleton)
encounter.start_encounter()

test("Sorcerer at (5,7)", get_position(sorcerer) == (5, 7))
test("Door is closed", not door.is_open)
test("Door blocks movement", not get_map().can_transition((6, 7), (7, 7), sorcerer.uuid))
test("Door blocks vision", not get_map().can_see_transition((6, 7), (7, 7), sorcerer.uuid))

# Sorcerer should NOT see skeleton through closed door
test("Skeleton NOT visible through closed door", skeleton.uuid not in sorcerer.senses.entities)

# --- Move sorcerer to (6,7), next to the door ---
print("\n--- Move to door ---")
# Start sorcerer's turn
encounter.start_turn()
move_entity(sorcerer, (6, 7))
Entity.update_all_entities_senses()

test("Sorcerer at (6,7)", get_position(sorcerer) == (6, 7))

# Door should be visible as an object
test("Door visible in senses.objects", door.uuid in sorcerer.senses.objects)

# --- Get available actions (this was hanging) ---
print("\n--- Available actions ---")
actions = get_available_actions(sorcerer)
test("get_available_actions returned", actions is not None)

# Find the Open Door action among self_actions (use actions route there for SELF target)
open_door_actions = [a for a in actions.self_actions if "Open Door" in (a.template_name or "")]
test("Open Door in available actions", len(open_door_actions) > 0)

# --- Open the door ---
print("\n--- Open door ---")
if open_door_actions:
    result = execute_use_action(sorcerer, door.uuid, "Open Door")
    test("Open Door executed", result is not None and not result.canceled)
else:
    print("  SKIP: No Open Door action found")

test("Door is now open", door.is_open)
test("Door no longer blocks movement", get_map().can_transition((6, 7), (7, 7), sorcerer.uuid))
test("Door no longer blocks vision", get_map().can_see_transition((6, 7), (7, 7), sorcerer.uuid))

# --- After opening, sorcerer should see the skeleton ---
Entity.update_all_entities_senses()
test("Skeleton visible through open door", skeleton.uuid in sorcerer.senses.entities)

# --- Close Door should now be available ---
print("\n--- Close door available ---")
actions2 = get_available_actions(sorcerer)
close_door_actions = [a for a in actions2.self_actions if "Close Door" in (a.template_name or "")]
test("Close Door in available actions", len(close_door_actions) > 0)

# --- Summary ---
print(f"\n{'=' * 60}")
print(f"Results: {passed} passed, {failed} failed")
print(f"{'=' * 60}")
sys.exit(1 if failed > 0 else 0)
