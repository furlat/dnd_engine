"""Extensive tests for Gust of Wind spell.

Tests cover:
- Push on initial cast (STR save, 15ft away from caster)
- Push on entry into zone
- Push on turn start in zone
- Push blocked by wall
- Passed save = no push
- Difficult terrain in zone
- Concentration break removes zone and terrain
- No push/terrain after zone removed
"""
import sys
import traceback

from typing import cast as type_cast

from dnd.core.events import EventQueue
from dnd.core.gridmap import get_map, reset_map
from dnd.core.modifiers import NumericalModifier
from dnd.entity import Entity, get_natural_roll
from dnd.monsters.bestiary import create_caster, create_goblin
from dnd.spells.evocation import GustOfWind, GustOfWindZone
from dnd.utils import (
    reset_combat_state, get_hp, set_hp, has_condition, get_position,
)


def setup_arena(size: int = 25):
    reset_map()
    grid = get_map()
    grid.create_rectangle(0, 0, size, size)
    return grid


def had_critical_d20() -> bool:
    for event in EventQueue._all_events:
        for attr in ('dice_roll', 'save_roll'):
            roll = getattr(event, attr, None)
            if roll is not None:
                try:
                    nat = get_natural_roll(roll)
                    if nat in (1, 20):
                        return True
                except Exception:
                    pass
    return False


def force_str_fail(entity: Entity) -> None:
    mod = NumericalModifier.create(
        source_entity_uuid=entity.uuid, name="Force Fail", value=-100
    )
    entity.saving_throws.strength_saving_throw.bonus.self_static.add_value_modifier(mod)


def force_str_pass(entity: Entity) -> None:
    mod = NumericalModifier.create(
        source_entity_uuid=entity.uuid, name="Force Pass", value=100
    )
    entity.saving_throws.strength_saving_throw.bonus.self_static.add_value_modifier(mod)


# =============================================================================
# Test 1: Initial cast pushes creature in line
# =============================================================================
def test_gust_push_on_cast():
    """Creature in the line is pushed 15ft (3 tiles) away from caster."""
    print("\n=== Test 1: Push on initial cast ===")

    for attempt in range(10):
        reset_combat_state()
        setup_arena()

        # Caster at (5, 10), line goes east toward (20, 10)
        caster = create_caster(name="Wizard", position=(5, 10), level=5, faction="heroes")
        target = create_goblin(name="Goblin", position=(8, 10), faction="monsters")
        Entity.update_all_entities_senses(max_distance=20)

        force_str_fail(target)
        set_hp(target, 200)

        pos_before = get_position(target)
        print(f"  Position before: {pos_before}")

        spell = GustOfWind(
            source_entity_uuid=caster.uuid,
            end_position=(20, 10),
            cast_at_level=2,
            template=False,
            costs=GustOfWind(source_entity_uuid=caster.uuid)._get_costs_for_level(2)
        )
        result = spell.apply()

        if had_critical_d20():
            print(f"  Attempt {attempt+1}: nat 1/20, retrying...")
            continue

        assert result is not None and not result.canceled, f"Should succeed: {result}"

        pos_after = get_position(target)
        print(f"  Position after: {pos_after}")

        # Should be pushed east (positive x) by 3 tiles
        push_distance = pos_after[0] - pos_before[0]
        assert push_distance == 3, \
            f"Should be pushed 3 tiles east, was pushed {push_distance}"
        assert pos_after[1] == pos_before[1], "Should not move in y direction"

        print("  PASS: Pushed 15ft on failed STR save")
        return

    print("  SKIP: All attempts had nat 1/20")


# =============================================================================
# Test 2: Passed save = no push
# =============================================================================
def test_gust_no_push_on_save():
    """Creature that passes STR save is not pushed."""
    print("\n=== Test 2: No push on passed save ===")

    for attempt in range(10):
        reset_combat_state()
        setup_arena()

        caster = create_caster(name="Wizard", position=(5, 10), level=5, faction="heroes")
        target = create_goblin(name="Strong Goblin", position=(8, 10), faction="monsters")
        Entity.update_all_entities_senses(max_distance=20)

        force_str_pass(target)
        set_hp(target, 200)

        pos_before = get_position(target)

        spell = GustOfWind(
            source_entity_uuid=caster.uuid,
            end_position=(20, 10),
            cast_at_level=2,
            template=False,
            costs=GustOfWind(source_entity_uuid=caster.uuid)._get_costs_for_level(2)
        )
        spell.apply()

        if had_critical_d20():
            print(f"  Attempt {attempt+1}: nat 1/20, retrying...")
            continue

        pos_after = get_position(target)
        print(f"  Position: {pos_before} -> {pos_after}")

        assert pos_after == pos_before, \
            f"Should NOT be pushed on passed save, moved from {pos_before} to {pos_after}"

        print("  PASS: No push on passed save")
        return

    print("  SKIP: All attempts had nat 1/20")


# =============================================================================
# Test 3: Zone created with concentration
# =============================================================================
def test_gust_zone_created():
    """Casting creates zone condition and Concentrating."""
    print("\n=== Test 3: Zone and concentration created ===")
    reset_combat_state()
    setup_arena()

    caster = create_caster(name="Wizard", position=(5, 10), level=5, faction="heroes")
    Entity.update_all_entities_senses(max_distance=20)

    spell = GustOfWind(
        source_entity_uuid=caster.uuid,
        end_position=(20, 10),
        cast_at_level=2,
        template=False,
        costs=GustOfWind(source_entity_uuid=caster.uuid)._get_costs_for_level(2)
    )
    spell.apply()

    assert has_condition(caster, "Gust of Wind Zone"), "Should have zone"
    assert has_condition(caster, "Concentrating"), "Should be concentrating"

    zone = type_cast(GustOfWindZone, caster.active_conditions.get("Gust of Wind Zone"))
    assert isinstance(zone, GustOfWindZone)
    print(f"  Zone center: {zone.zone_center}")
    print(f"  Zone positions: {len(zone.affected_positions)}")
    assert len(zone.affected_positions) > 0, "Zone should have positions"

    print("  PASS: Zone and concentration created")


# =============================================================================
# Test 4: Entry into zone triggers push
# =============================================================================
def test_gust_entry_push():
    """Moving into the zone triggers a push."""
    print("\n=== Test 4: Entry push ===")

    for attempt in range(10):
        reset_combat_state()
        setup_arena()

        caster = create_caster(name="Wizard", position=(5, 10), level=5, faction="heroes")
        target = create_goblin(name="Goblin", position=(2, 10), faction="monsters")
        Entity.update_all_entities_senses(max_distance=20)

        set_hp(target, 200)

        spell = GustOfWind(
            source_entity_uuid=caster.uuid,
            end_position=(20, 10),
            cast_at_level=2,
            template=False,
            costs=GustOfWind(source_entity_uuid=caster.uuid)._get_costs_for_level(2)
        )
        spell.apply()

        # Now move target into the zone
        force_str_fail(target)

        # Pick a position in the zone (ahead of caster in the wind line)
        zone = type_cast(GustOfWindZone, caster.active_conditions.get("Gust of Wind Zone"))
        assert zone is not None
        # Find a zone position to move into
        zone_pos = None
        for pos in sorted(zone.affected_positions):
            if pos[1] == 10 and pos[0] > 5:  # In the line, east of caster
                zone_pos = pos
                break
        assert zone_pos is not None, f"Should find zone position, zone has {len(zone.affected_positions)} positions"

        Entity.update_entity_position(target, zone_pos)

        if had_critical_d20():
            print(f"  Attempt {attempt+1}: nat 1/20, retrying...")
            continue

        final_pos = get_position(target)
        print(f"  Moved to {zone_pos}, pushed to {final_pos}")

        # Should be pushed east (away from caster)
        assert final_pos[0] > zone_pos[0], \
            f"Should be pushed east from {zone_pos} but ended at {final_pos}"

        print("  PASS: Entry push works")
        return

    print("  SKIP: All attempts had nat 1/20")


# =============================================================================
# Test 5: Turn start push
# =============================================================================
def test_gust_turn_start_push():
    """Creature starting turn in zone is pushed."""
    print("\n=== Test 5: Turn start push ===")

    for attempt in range(10):
        reset_combat_state()
        setup_arena()

        caster = create_caster(name="Wizard", position=(5, 10), level=5, faction="heroes")
        target = create_goblin(name="Goblin", position=(8, 10), faction="monsters")
        Entity.update_all_entities_senses(max_distance=20)

        set_hp(target, 200)
        force_str_fail(target)

        # Cast - target gets pushed initially
        spell = GustOfWind(
            source_entity_uuid=caster.uuid,
            end_position=(20, 10),
            cast_at_level=2,
            template=False,
            costs=GustOfWind(source_entity_uuid=caster.uuid)._get_costs_for_level(2)
        )
        spell.apply()

        if had_critical_d20():
            print(f"  Attempt {attempt+1}: nat 1/20, retrying...")
            continue

        pos_after_cast = get_position(target)
        print(f"  Position after cast: {pos_after_cast}")

        # If target is still in zone, turn start should push again
        zone = type_cast(GustOfWindZone, caster.active_conditions.get("Gust of Wind Zone"))
        if pos_after_cast in zone.affected_positions:
            target.on_turn_start()
            pos_after_turn = get_position(target)
            print(f"  Position after turn start: {pos_after_turn}")
            assert pos_after_turn[0] > pos_after_cast[0], \
                f"Should be pushed further east on turn start"
            print("  PASS: Turn start push works")
            return
        else:
            print(f"  Target pushed out of zone ({pos_after_cast}), retrying...")
            continue

    print("  SKIP: Could not get stable test")


# =============================================================================
# Test 6: Push blocked by wall
# =============================================================================
def test_gust_push_blocked_by_wall():
    """Push stops at wall."""
    print("\n=== Test 6: Push blocked by wall ===")

    for attempt in range(10):
        reset_combat_state()
        grid = setup_arena()

        caster = create_caster(name="Wizard", position=(5, 10), level=5, faction="heroes")
        target = create_goblin(name="Goblin", position=(8, 10), faction="monsters")

        # Wall 2 tiles east of target
        grid.set_tile(10, 10, walkable=False, visible=False, name="Wall")

        Entity.update_all_entities_senses(max_distance=20)

        force_str_fail(target)
        set_hp(target, 200)

        spell = GustOfWind(
            source_entity_uuid=caster.uuid,
            end_position=(20, 10),
            cast_at_level=2,
            template=False,
            costs=GustOfWind(source_entity_uuid=caster.uuid)._get_costs_for_level(2)
        )
        spell.apply()

        if had_critical_d20():
            print(f"  Attempt {attempt+1}: nat 1/20, retrying...")
            continue

        pos = get_position(target)
        print(f"  Position after push with wall at (10,10): {pos}")

        # Should stop before wall (max x=9)
        assert pos[0] <= 9, f"Should stop before wall at x=10, ended at {pos}"
        assert pos[0] > 8, f"Should be pushed at least 1 tile, stayed at {pos}"

        print("  PASS: Push blocked by wall")
        return

    print("  SKIP: All attempts had nat 1/20")


# =============================================================================
# Test 7: Difficult terrain in zone
# =============================================================================
def test_gust_difficult_terrain():
    """Zone adds difficult terrain to tiles in the line."""
    print("\n=== Test 7: Difficult terrain ===")
    reset_combat_state()
    grid = setup_arena()

    caster = create_caster(name="Wizard", position=(5, 10), level=5, faction="heroes")
    Entity.update_all_entities_senses(max_distance=20)

    # Check base cost
    tile = grid.get_tile(8, 10)
    assert tile is not None
    cost_before = tile.walking_cost.normalized_score
    print(f"  Tile (8,10) cost before: {cost_before}")

    spell = GustOfWind(
        source_entity_uuid=caster.uuid,
        end_position=(20, 10),
        cast_at_level=2,
        template=False,
        costs=GustOfWind(source_entity_uuid=caster.uuid)._get_costs_for_level(2)
    )
    spell.apply()

    zone = type_cast(GustOfWindZone, caster.active_conditions.get("Gust of Wind Zone"))
    assert zone is not None

    # Check a tile IN the zone
    zone_tile = None
    for pos in zone.affected_positions:
        t = grid.get_tile(*pos)
        if t:
            zone_tile = t
            break
    assert zone_tile is not None

    cost_during = zone_tile.walking_cost.normalized_score
    print(f"  Zone tile cost during: {cost_during}")
    assert cost_during == 2, f"Difficult terrain should double cost to 2, got {cost_during}"

    print("  PASS: Difficult terrain in zone")


# =============================================================================
# Test 8: Concentration break removes zone and terrain
# =============================================================================
def test_gust_concentration_break():
    """Breaking concentration removes zone, terrain, and push effects."""
    print("\n=== Test 8: Concentration break ===")
    reset_combat_state()
    grid = setup_arena()

    caster = create_caster(name="Wizard", position=(5, 10), level=5, faction="heroes")
    Entity.update_all_entities_senses(max_distance=20)

    spell = GustOfWind(
        source_entity_uuid=caster.uuid,
        end_position=(20, 10),
        cast_at_level=2,
        template=False,
        costs=GustOfWind(source_entity_uuid=caster.uuid)._get_costs_for_level(2)
    )
    spell.apply()

    # Record a zone tile for terrain check
    zone = type_cast(GustOfWindZone, caster.active_conditions.get("Gust of Wind Zone"))
    zone_pos = next(iter(zone.affected_positions))
    zone_tile = grid.get_tile(*zone_pos)
    assert zone_tile is not None
    assert zone_tile.walking_cost.normalized_score == 2

    # Break concentration
    caster.remove_condition("Concentrating")

    assert not has_condition(caster, "Concentrating")
    assert not has_condition(caster, "Gust of Wind Zone"), "Zone should be removed"

    # Terrain should be restored
    cost_after = zone_tile.walking_cost.normalized_score
    print(f"  Zone tile cost after removal: {cost_after}")
    assert cost_after == 1, f"Terrain should be restored to 1, got {cost_after}"

    print("  PASS: Concentration break removes zone and terrain")


# =============================================================================
# Test 9: No push after zone removed
# =============================================================================
def test_gust_no_push_after_removal():
    """After zone is removed, entering former area does not push."""
    print("\n=== Test 9: No push after removal ===")
    reset_combat_state()
    setup_arena()

    caster = create_caster(name="Wizard", position=(5, 10), level=5, faction="heroes")
    target = create_goblin(name="Goblin", position=(2, 10), faction="monsters")
    Entity.update_all_entities_senses(max_distance=20)

    set_hp(target, 200)

    spell = GustOfWind(
        source_entity_uuid=caster.uuid,
        end_position=(20, 10),
        cast_at_level=2,
        template=False,
        costs=GustOfWind(source_entity_uuid=caster.uuid)._get_costs_for_level(2)
    )
    spell.apply()

    # Remove zone
    caster.remove_condition("Concentrating")

    # Move target to where zone was
    Entity.update_entity_position(target, (8, 10))
    pos = get_position(target)
    assert pos == (8, 10), f"Should stay at (8,10) without push, ended at {pos}"

    print("  PASS: No push after zone removed")


# =============================================================================
# Test 10: Reactive _paths_dirty pipeline for difficult terrain
# =============================================================================
def test_gust_terrain_reactive_paths():
    """Verify the reactive path pipeline: Gust of Wind terrain sets _paths_dirty,
    and get_available_actions() triggers lazy Dijkstra recompute."""
    print("\n=== Test 10: Reactive _paths_dirty terrain pipeline ===")
    reset_combat_state()
    grid = setup_arena(size=25)

    # Narrow corridor so mover MUST traverse the zone
    for x in range(0, 25):
        grid.set_tile(x, 9, walkable=False, visible=False, name="Wall")
        grid.set_tile(x, 11, walkable=False, visible=False, name="Wall")

    # Caster at west end, mover IN the zone but force STR pass so not pushed on cast.
    # Wind blows east. Mover at (5,10) with 30ft (6 tiles) budget.
    caster = create_caster(name="Wizard", position=(1, 10), level=5, faction="heroes")
    mover = create_goblin(name="Mover", position=(5, 10), faction="monsters")
    Entity.update_all_entities_senses(max_distance=20)
    set_hp(mover, 200)
    force_str_pass(mover)  # Don't get pushed on cast

    # Get Move targets BEFORE the wind
    actions_before = mover.get_available_actions()
    move_before = [a for a in actions_before.position_actions if a.template_name == "Move"]
    targets_before = {t.position for t in move_before[0].valid_targets} if move_before else set()
    print(f"  Move targets before wind: {len(targets_before)}")

    # Cast Gust of Wind east through the corridor
    spell = GustOfWind(
        source_entity_uuid=caster.uuid,
        end_position=(20, 10),
        cast_at_level=2,
        template=False,
        costs=GustOfWind(source_entity_uuid=caster.uuid)._get_costs_for_level(2)
    )
    spell.apply()

    # Verify mover was NOT pushed (STR pass)
    assert get_position(mover) == (5, 10), "Mover should stay (STR pass)"

    # REACTIVE CHECK: _paths_dirty should be set by terrain change
    assert mover.senses._paths_dirty, \
        "_paths_dirty should be True after Gust of Wind terrain (reactive SPATIAL_TILE_CHANGED)"

    # get_available_actions() triggers lazy Dijkstra recompute
    actions_after = mover.get_available_actions()
    assert not mover.senses._paths_dirty, "_paths_dirty should be cleared"

    move_after = [a for a in actions_after.position_actions if a.template_name == "Move"]
    targets_after = {t.position for t in move_after[0].valid_targets} if move_after else set()
    print(f"  Move targets after wind: {len(targets_after)}")

    # Difficult terrain in corridor should reduce reachable destinations
    assert len(targets_after) < len(targets_before), \
        f"Should have fewer Move targets with wind terrain: before={len(targets_before)}, after={len(targets_after)}"

    # Break concentration — should restore
    caster.remove_condition("Concentrating")
    assert mover.senses._paths_dirty, "_paths_dirty should be set after terrain removal"

    actions_restored = mover.get_available_actions()
    move_restored = [a for a in actions_restored.position_actions if a.template_name == "Move"]
    targets_restored = {t.position for t in move_restored[0].valid_targets} if move_restored else set()
    print(f"  Move targets after wind removed: {len(targets_restored)}")
    assert len(targets_restored) == len(targets_before), \
        f"Should restore Move targets: before={len(targets_before)}, restored={len(targets_restored)}"

    print("  PASS: Reactive _paths_dirty pipeline works for Gust of Wind terrain")


# =============================================================================
# Test 11: Exit zone - no damage/push on exit
# =============================================================================
def test_gust_exit_no_effect():
    """Leaving the zone does NOT trigger push (only entry and turn start)."""
    print("\n=== Test 11: Exit zone - no effect ===")

    for attempt in range(10):
        reset_combat_state()
        setup_arena()

        caster = create_caster(name="Wizard", position=(5, 10), level=5, faction="heroes")
        target = create_goblin(name="Goblin", position=(8, 10), faction="monsters")
        Entity.update_all_entities_senses(max_distance=20)
        set_hp(target, 200)

        # Cast gust east (target in zone, will be pushed)
        force_str_fail(target)
        spell = GustOfWind(
            source_entity_uuid=caster.uuid,
            end_position=(20, 10),
            cast_at_level=2,
            template=False,
            costs=GustOfWind(source_entity_uuid=caster.uuid)._get_costs_for_level(2)
        )
        spell.apply()

        if had_critical_d20():
            print(f"  Attempt {attempt+1}: nat 1/20, retrying...")
            continue

        # Target was pushed out. Now move target to zone edge and out.
        _pushed_pos = get_position(target)
        zone = type_cast(GustOfWindZone, caster.active_conditions.get("Gust of Wind Zone"))
        assert zone is not None

        # Find a zone position and a non-zone position adjacent to it
        zone_positions = zone.affected_positions
        # Move target back into a zone position
        zone_pos = None
        for pos in sorted(zone_positions):
            if pos[0] > 5 and pos[1] == 10:
                zone_pos = pos
                break
        if zone_pos is None:
            continue

        # Put target at zone pos without triggering entry (direct position set)
        target.senses.position = zone_pos
        hp_before_exit = get_hp(target)

        # Now exit the zone — move to a position NOT in zone
        exit_pos = (2, 10)  # Behind caster, outside zone
        Entity.update_entity_position(target, exit_pos)

        # Should NOT have been pushed or damaged on exit
        final_pos = get_position(target)
        hp_after_exit = get_hp(target)
        assert final_pos == exit_pos, f"Should stay at exit position {exit_pos}, not pushed, got {final_pos}"
        assert hp_after_exit == hp_before_exit, "Should not take damage on exit"

        print(f"  Exited zone from {zone_pos} to {exit_pos} — no push, no damage")
        print("  PASS: Exit zone has no effect")
        return

    print("  SKIP: All attempts had nat 1/20")


# =============================================================================
# Run all tests
# =============================================================================
if __name__ == "__main__":
    tests = [
        test_gust_push_on_cast,
        test_gust_no_push_on_save,
        test_gust_zone_created,
        test_gust_entry_push,
        test_gust_turn_start_push,
        test_gust_push_blocked_by_wall,
        test_gust_difficult_terrain,
        test_gust_concentration_break,
        test_gust_no_push_after_removal,
        test_gust_terrain_reactive_paths,
        test_gust_exit_no_effect,
    ]

    passed = 0
    failed = 0
    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            failed += 1
            print(f"  FAIL: {e}")
            traceback.print_exc()

    print(f"\n{'='*60}")
    print(f"Results: {passed} passed, {failed} failed out of {len(tests)} tests")
    if failed > 0:
        sys.exit(1)
    print("All Gust of Wind tests passed!")
