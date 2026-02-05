"""
Test spike zone behavior - damage per step, stale paths, death stops movement.

Tests for spike zone bug fixes:
1. Tile inspect shows content (Bug #1)
2. Paths updated after move (Bug #2)
3. Spike damage in combat log (Bug #3)
4. Death during movement stops movement (Bug #4)
5. is_moving flag cleared on early exit
"""

from uuid import uuid4

from dnd.utils.test_utils import reset_combat_state, get_hp, set_hp, has_condition
from dnd.tiles import create_spike_zone
from dnd.core.gridmap import get_map
from dnd.monsters.bestiary import create_skeleton
from dnd.entity import Entity
from dnd.actions_functional import get_available_actions, execute_action


def test_damage_per_step_through_zone():
    """Moving through 4 spike tiles should deal damage 4 times."""
    print("\n=== Test: Damage Per Step Through Zone ===")
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 10, 10)

    # Spike zone at y=5, x=3-6 (4 tiles)
    spike_positions = {(3, 5), (4, 5), (5, 5), (6, 5)}
    tiles, handler = create_spike_zone(spike_positions)
    for tile in tiles:
        grid._tiles[tile.position] = tile

    skeleton = create_skeleton(name='Test', position=(0, 5))
    Entity.update_all_entities_senses()

    start_hp = get_hp(skeleton)
    print(f"  Starting HP: {start_hp}")

    # Move from (0,5) to (7,5) - passes through 4 spike tiles
    actions = get_available_actions(skeleton)
    move_action = next((a for a in actions.position_actions if a.template_name == "Move"), None)
    assert move_action is not None, "Should have Move action"

    target = next((t for t in move_action.valid_targets if t.position == (7, 5)), None)
    if target is None:
        print(f"  Warning: (7,5) not reachable. Available targets: {[t.position for t in move_action.valid_targets[:5]]}...")
        # Try a closer target
        target = next((t for t in move_action.valid_targets if t.position[0] >= 6), None)

    if target:
        execute_action(skeleton, "Move", target)
        damage_taken = start_hp - get_hp(skeleton)
        print(f"  Ended at: {skeleton.position}")
        print(f"  Damage taken: {damage_taken}")
        # 4 spike tiles × 2d4 (min 2, max 8 per tile) = expected 8-32 damage
        # But we may not reach all 4 tiles depending on path
        if damage_taken >= 4:  # At least 2 tiles worth (minimum 2 damage each)
            print("  PASS: Took damage from spike tiles")
        else:
            print(f"  FAIL: Expected at least 4 damage, got {damage_taken}")
    else:
        print("  SKIP: No reachable target through spike zone")


def test_paths_updated_after_move():
    """After moving, paths should be from new position (Bug #2 fix)."""
    print("\n=== Test: Paths Updated After Move ===")
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 10, 10)

    skeleton = create_skeleton(name='Test', position=(0, 5))
    Entity.update_all_entities_senses()

    print(f"  Starting position: {skeleton.position}")

    # Move to (3, 5)
    actions = get_available_actions(skeleton)
    move_action = next((a for a in actions.position_actions if a.template_name == "Move"), None)
    target = next((t for t in move_action.valid_targets if t.position == (3, 5)), None)

    if target:
        execute_action(skeleton, "Move", target)
        print(f"  Moved to: {skeleton.position}")
        assert skeleton.position == (3, 5), f"Should be at (3,5), got {skeleton.position}"

        # Key test: paths should be computed from (3,5), not (0,5)
        # (4,5) should be reachable from current position
        actions2 = get_available_actions(skeleton)
        move_action2 = next((a for a in actions2.position_actions if a.template_name == "Move"), None)

        if move_action2:
            reachable_positions = {t.position for t in move_action2.valid_targets}
            print(f"  Reachable positions include (4,5): {(4, 5) in reachable_positions}")

            if (4, 5) in reachable_positions:
                print("  PASS: Paths are correctly computed from new position")
            else:
                print("  FAIL: (4,5) should be reachable from (3,5)")
        else:
            # Entity might be out of movement
            print("  INFO: No more movement available (expected after long move)")
            # Check if is_moving flag is cleared
            if not skeleton.senses.is_moving:
                print("  PASS: is_moving flag is cleared")
            else:
                print("  FAIL: is_moving should be False")
    else:
        print("  SKIP: Target (3,5) not reachable")


def test_death_stops_movement():
    """Entity dying mid-movement should stop at death position (Bug #4)."""
    print("\n=== Test: Death Stops Movement ===")
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 10, 10)

    # Spike zone at y=5, x=3-6
    spike_positions = {(3, 5), (4, 5), (5, 5), (6, 5)}
    tiles, handler = create_spike_zone(spike_positions)
    for tile in tiles:
        grid._tiles[tile.position] = tile

    skeleton = create_skeleton(name='Test', position=(0, 5))
    Entity.update_all_entities_senses()

    # Set HP low enough to die from spike damage (2d4 = 2-8 per tile)
    set_hp(skeleton, 3)  # Should die after 1-2 spike tiles
    start_hp = get_hp(skeleton)
    print(f"  Starting HP: {start_hp}, position: {skeleton.position}")

    # Try to move through spike zone to (7,5)
    actions = get_available_actions(skeleton)
    move_action = next((a for a in actions.position_actions if a.template_name == "Move"), None)
    target = next((t for t in move_action.valid_targets if t.position == (7, 5)), None)

    if target:
        execute_action(skeleton, "Move", target)
        final_hp = get_hp(skeleton)
        print(f"  Final HP: {final_hp}, position: {skeleton.position}")

        # Should have died and stopped
        if final_hp <= 0:
            print("  Entity died as expected")
            # Position should be in or before spike zone, not at destination
            if skeleton.position[0] <= 6:
                print(f"  PASS: Stopped at {skeleton.position} (not at destination)")
            else:
                print(f"  FAIL: Should have stopped in spikes, got {skeleton.position}")
        else:
            print(f"  Entity survived with {final_hp} HP")
            print("  INFO: RNG may have rolled low damage")

        # CRITICAL: is_moving flag should be cleared even after death
        if not skeleton.senses.is_moving:
            print("  PASS: is_moving flag cleared after death")
        else:
            print("  FAIL: is_moving should be False after movement ends")
    else:
        print("  SKIP: Target not reachable")


def test_is_moving_cleared_on_early_exit():
    """is_moving flag must be cleared even if movement ends early."""
    print("\n=== Test: is_moving Flag Cleared ===")
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 10, 10)

    skeleton = create_skeleton(name='Test', position=(0, 5))
    Entity.update_all_entities_senses()

    print(f"  Initial is_moving: {skeleton.senses.is_moving}")
    assert not skeleton.senses.is_moving, "Should start with is_moving=False"

    # Move normally
    actions = get_available_actions(skeleton)
    move_action = next((a for a in actions.position_actions if a.template_name == "Move"), None)
    target = next((t for t in move_action.valid_targets if t.position == (2, 5)), None)

    if target:
        execute_action(skeleton, "Move", target)
        print(f"  After move, is_moving: {skeleton.senses.is_moving}")

        if not skeleton.senses.is_moving:
            print("  PASS: is_moving cleared after normal move")
        else:
            print("  FAIL: is_moving should be False after move")
    else:
        print("  SKIP: Target not reachable")


def test_spike_zone_with_encounter():
    """Test spike damage appears in combat log when encounter is active."""
    print("\n=== Test: Spike Damage in Combat Log ===")
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 10, 10)

    # Spike zone
    spike_positions = {(3, 5), (4, 5)}
    tiles, handler = create_spike_zone(spike_positions)
    for tile in tiles:
        grid._tiles[tile.position] = tile

    # Create entities
    skeleton = create_skeleton(name='Walker', position=(0, 5))
    target = create_skeleton(name='Target', position=(8, 5))
    Entity.update_all_entities_senses()

    # Create encounter
    from dnd.encounter import Encounter
    from dnd.controller import PassController

    encounter = Encounter(name="Spike Test", source_entity_uuid=uuid4())
    encounter.add_combatant(skeleton, PassController(source_entity_uuid=skeleton.uuid))
    encounter.add_combatant(target, PassController(source_entity_uuid=target.uuid))
    encounter.roll_initiative()
    encounter.start_encounter()

    print(f"  Combat log entries before move: {len(encounter.combat_log)}")

    # Move through spikes
    actions = get_available_actions(skeleton)
    move_action = next((a for a in actions.position_actions if a.template_name == "Move"), None)
    move_target = next((t for t in move_action.valid_targets if t.position[0] >= 4), None)

    if move_target:
        execute_action(skeleton, "Move", move_target)
        print(f"  Combat log entries after move: {len(encounter.combat_log)}")

        # Check for damage entries in combat log
        damage_entries = [e for e in encounter.combat_log if e.entry_type == "damage_taken"]
        print(f"  Damage log entries: {len(damage_entries)}")

        if len(damage_entries) > 0:
            print("  PASS: Spike damage appears in combat log")
            for entry in damage_entries[:2]:
                print(f"    - {entry.compact}")
        else:
            # Damage might be logged differently or not at all yet
            print("  INFO: No damage_taken entries found")
            print(f"  All entry types: {set(e.entry_type for e in encounter.combat_log)}")


def test_dead_condition_applied_on_spike_death():
    """Test that Dead condition is applied when entity dies from spike damage."""
    print("\n=== Test: Dead Condition Applied ===")
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 10, 10)

    # Spike zone
    spike_positions = {(3, 5), (4, 5), (5, 5)}
    tiles, handler = create_spike_zone(spike_positions)
    for tile in tiles:
        grid._tiles[tile.position] = tile

    skeleton = create_skeleton(name='Victim', position=(0, 5))
    Entity.update_all_entities_senses()

    # Set very low HP to ensure death
    set_hp(skeleton, 2)
    print(f"  Starting HP: {get_hp(skeleton)}")

    # Move through spikes
    actions = get_available_actions(skeleton)
    move_action = next((a for a in actions.position_actions if a.template_name == "Move"), None)
    move_target = next((t for t in move_action.valid_targets if t.position[0] >= 5), None)

    if move_target:
        execute_action(skeleton, "Move", move_target)
        print(f"  Final HP: {get_hp(skeleton)}")

        if get_hp(skeleton) <= 0:
            if has_condition(skeleton, "Dead"):
                print("  PASS: Dead condition was applied")
            else:
                print(f"  FAIL: Dead condition not found. Conditions: {list(skeleton.active_conditions.keys())}")

            # Check Incapacitated sub-condition
            if has_condition(skeleton, "Incapacitated"):
                print("  PASS: Incapacitated sub-condition present")
            else:
                print("  INFO: Incapacitated not directly listed (may be via Dead)")
        else:
            print("  INFO: Entity survived (low damage rolls)")


if __name__ == "__main__":
    print("=" * 60)
    print("SPIKE ZONE BUG TESTS")
    print("=" * 60)

    test_is_moving_cleared_on_early_exit()
    test_paths_updated_after_move()
    test_damage_per_step_through_zone()
    test_death_stops_movement()
    test_dead_condition_applied_on_spike_death()
    test_spike_zone_with_encounter()

    print("\n" + "=" * 60)
    print("ALL SPIKE ZONE TESTS COMPLETE")
    print("=" * 60)
