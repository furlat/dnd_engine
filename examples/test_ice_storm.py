"""Extensive tests for Ice Storm spell.

Tests cover:
- Failed save → full damage (2d8 bludg + 4d6 cold)
- Successful save → half damage
- Upcasting adds bludgeoning dice (+1d8 per level above 4th)
- Difficult terrain applied for 1 round, then expires
- NOT concentration
- Cylinder AoE hits behind corners (ignores barriers)
- Multiple targets in cylinder all take damage
"""
import sys
import traceback
from uuid import uuid4

from dnd.core.events import EventQueue
from dnd.core.gridmap import get_map, reset_map
from dnd.core.modifiers import NumericalModifier
from dnd.entity import Entity, get_natural_roll
from dnd.monsters.bestiary import create_sorcerer, create_goblin
from dnd.spells.evocation import IceStorm, IceStormTerrain
from dnd.utils import (
    reset_combat_state, get_hp, set_hp, has_condition,
)


def setup_arena(size: int = 20):
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


def force_save_fail(entity: Entity) -> None:
    """Add -100 to DEX save to guarantee failure."""
    mod = NumericalModifier.create(
        source_entity_uuid=entity.uuid, name="Force Fail", value=-100
    )
    entity.saving_throws.dexterity_saving_throw.bonus.self_static.add_value_modifier(mod)


def force_save_pass(entity: Entity) -> None:
    """Add +100 to DEX save to guarantee success."""
    mod = NumericalModifier.create(
        source_entity_uuid=entity.uuid, name="Force Pass", value=100
    )
    entity.saving_throws.dexterity_saving_throw.bonus.self_static.add_value_modifier(mod)


# =============================================================================
# Test 1: Ice Storm - failed save = full damage
# =============================================================================
def test_ice_storm_failed_save():
    """On failed DEX save, target takes full 2d8 + 4d6 damage."""
    print("\n=== Test 1: Ice Storm failed save ===")

    for attempt in range(10):
        reset_combat_state()
        setup_arena()

        caster = create_sorcerer(name="Wizard", position=(5, 5), level=5, faction="heroes")
        target = create_goblin(name="Goblin", position=(10, 5), faction="monsters")
        Entity.update_all_entities_senses()

        force_save_fail(target)
        set_hp(target, 200)
        hp_before = get_hp(target)

        spell = IceStorm(
            source_entity_uuid=caster.uuid,
            end_position=(10, 5),
            cast_at_level=4,
            template=False,
            costs=IceStorm(source_entity_uuid=caster.uuid)._get_costs_for_level(4)
        )
        result = spell.apply()

        if had_critical_d20():
            print(f"  Attempt {attempt+1}: nat 1/20, retrying...")
            continue

        assert result is not None and not result.canceled, f"Should succeed: {result}"

        damage = hp_before - get_hp(target)
        # 2d8 (2-16) + 4d6 (4-24) = 6-40
        print(f"  Damage dealt: {damage}")
        assert damage >= 6, f"Minimum damage 6, got {damage}"
        assert damage <= 40, f"Maximum damage 40, got {damage}"

        print("  PASS: Full damage on failed save")
        return

    print("  SKIP: All attempts had nat 1/20")


# =============================================================================
# Test 2: Ice Storm - passed save = half damage
# =============================================================================
def test_ice_storm_passed_save():
    """On passed DEX save, target takes half damage."""
    print("\n=== Test 2: Ice Storm passed save ===")

    for attempt in range(10):
        reset_combat_state()
        setup_arena()

        caster = create_sorcerer(name="Wizard", position=(5, 5), level=5, faction="heroes")
        target = create_goblin(name="Goblin", position=(10, 5), faction="monsters")
        Entity.update_all_entities_senses()

        force_save_pass(target)
        set_hp(target, 200)
        hp_before = get_hp(target)

        spell = IceStorm(
            source_entity_uuid=caster.uuid,
            end_position=(10, 5),
            cast_at_level=4,
            template=False,
            costs=IceStorm(source_entity_uuid=caster.uuid)._get_costs_for_level(4)
        )
        result = spell.apply()

        if had_critical_d20():
            print(f"  Attempt {attempt+1}: nat 1/20, retrying...")
            continue

        assert result is not None and not result.canceled, f"Should succeed: {result}"

        damage = hp_before - get_hp(target)
        # Half of 6-40 = 3-20
        print(f"  Half damage dealt: {damage}")
        assert damage >= 3, f"Minimum half damage 3, got {damage}"
        assert damage <= 20, f"Maximum half damage 20, got {damage}"

        print("  PASS: Half damage on passed save")
        return

    print("  SKIP: All attempts had nat 1/20")


# =============================================================================
# Test 3: Ice Storm - upcasting adds bludgeoning dice
# =============================================================================
def test_ice_storm_upcast():
    """Upcasting adds +1d8 bludgeoning per level above 4th."""
    print("\n=== Test 3: Ice Storm upcasting ===")

    for attempt in range(10):
        reset_combat_state()
        setup_arena()

        caster = create_sorcerer(name="Wizard", position=(5, 5), level=5, faction="heroes")
        target = create_goblin(name="Goblin", position=(10, 5), faction="monsters")
        Entity.update_all_entities_senses()

        force_save_fail(target)
        set_hp(target, 300)
        hp_before = get_hp(target)

        # Cast at level 6: 4d8 + 4d6 (upcast +2d8)
        spell = IceStorm(
            source_entity_uuid=caster.uuid,
            end_position=(10, 5),
            cast_at_level=6,
            template=False,
            costs=IceStorm(source_entity_uuid=caster.uuid)._get_costs_for_level(6)
        )
        result = spell.apply()

        if had_critical_d20():
            print(f"  Attempt {attempt+1}: nat 1/20, retrying...")
            continue

        assert result is not None and not result.canceled, f"Should succeed: {result}"

        damage = hp_before - get_hp(target)
        # 4d8 (4-32) + 4d6 (4-24) = 8-56
        print(f"  Level 6 damage: {damage}")
        assert damage >= 8, f"Level 6 min damage 8, got {damage}"
        assert damage <= 56, f"Level 6 max damage 56, got {damage}"

        print("  PASS: Upcast adds bludgeoning dice")
        return

    print("  SKIP: All attempts had nat 1/20")


# =============================================================================
# Test 4: Ice Storm - difficult terrain applied and expires
# =============================================================================
def test_ice_storm_difficult_terrain():
    """Ice Storm creates difficult terrain for 1 round, then it expires."""
    print("\n=== Test 4: Ice Storm difficult terrain ===")
    reset_combat_state()
    setup_arena()

    caster = create_sorcerer(name="Wizard", position=(5, 5), level=5, faction="heroes")
    target = create_goblin(name="Goblin", position=(10, 5), faction="monsters")
    Entity.update_all_entities_senses()

    set_hp(target, 200)

    spell = IceStorm(
        source_entity_uuid=caster.uuid,
        end_position=(10, 5),
        cast_at_level=4,
        template=False,
        costs=IceStorm(source_entity_uuid=caster.uuid)._get_costs_for_level(4)
    )
    spell.apply()

    # Verify difficult terrain condition exists on caster
    assert has_condition(caster, "Ice Storm Terrain"), \
        "Should have Ice Storm Terrain condition"

    # Verify the zone condition is actually applied
    terrain_cond = caster.active_conditions.get("Ice Storm Terrain")
    assert terrain_cond is not None
    assert isinstance(terrain_cond, IceStormTerrain)
    print(f"  Terrain zone center: {terrain_cond.zone_center}")
    print(f"  Terrain duration: {terrain_cond.duration.duration}")

    # Advance 1 round - should expire
    caster.advance_duration("Ice Storm Terrain")

    assert not has_condition(caster, "Ice Storm Terrain"), \
        "Ice Storm Terrain should expire after 1 round"

    print("  PASS: Difficult terrain applied and expires after 1 round")


# =============================================================================
# Test 5: Ice Storm - NOT concentration
# =============================================================================
def test_ice_storm_not_concentration():
    """Ice Storm is NOT a concentration spell."""
    print("\n=== Test 5: Ice Storm NOT concentration ===")
    reset_combat_state()
    setup_arena()

    caster = create_sorcerer(name="Wizard", position=(5, 5), level=5, faction="heroes")
    target = create_goblin(name="Goblin", position=(10, 5), faction="monsters")
    Entity.update_all_entities_senses()

    set_hp(target, 200)

    spell = IceStorm(
        source_entity_uuid=caster.uuid,
        end_position=(10, 5),
        cast_at_level=4,
        template=False,
        costs=IceStorm(source_entity_uuid=caster.uuid)._get_costs_for_level(4)
    )
    spell.apply()

    assert not has_condition(caster, "Concentrating"), \
        "Ice Storm is NOT concentration"
    print("  PASS: Not concentration")


# =============================================================================
# Test 6: Cylinder AoE hits behind corners (ignores barriers)
# =============================================================================
def test_cylinder_ignores_walls():
    """Cylinder AoE comes from above — it should hit creatures BEHIND walls.

    This is the critical test: unlike Sphere/Cone/Line which use shadowcast
    to block through walls, Cylinder skips all barrier filtering.
    """
    print("\n=== Test 6: Cylinder AoE ignores walls ===")

    for attempt in range(10):
        reset_combat_state()
        grid = setup_arena(size=25)

        caster = create_sorcerer(name="Wizard", position=(3, 10), level=5, faction="heroes")

        # Place a wall in the middle of the target area
        # Cylinder centered at (10, 10) with radius 4 tiles (20ft)
        # Wall at x=10, dividing the cylinder
        for y_wall in range(8, 13):
            grid.set_tile(10, y_wall, walkable=False, visible=False, name="Wall")

        # Target IN FRONT of wall (caster side)
        front_target = create_goblin(name="Front Goblin", position=(9, 10), faction="monsters")
        # Target BEHIND wall (far side from caster)
        behind_target = create_goblin(name="Behind Goblin", position=(11, 10), faction="monsters")

        Entity.update_all_entities_senses(max_distance=20)

        force_save_fail(front_target)
        force_save_fail(behind_target)
        set_hp(front_target, 200)
        set_hp(behind_target, 200)
        front_hp = get_hp(front_target)
        behind_hp = get_hp(behind_target)

        # Cast Ice Storm centered between the wall and targets
        # Center at (10, 10) — but wall is there, so center at (9, 10)
        # Actually, let's center at (10, 10) — the cylinder comes from above
        # and the AoE should reach both sides of the wall
        spell = IceStorm(
            source_entity_uuid=caster.uuid,
            end_position=(9, 10),  # Center in front of wall, radius 4 reaches behind
            cast_at_level=4,
            template=False,
            costs=IceStorm(source_entity_uuid=caster.uuid)._get_costs_for_level(4)
        )
        result = spell.apply()

        if had_critical_d20():
            print(f"  Attempt {attempt+1}: nat 1/20, retrying...")
            continue

        assert result is not None and not result.canceled, f"Should succeed: {result}"

        front_damage = front_hp - get_hp(front_target)
        behind_damage = behind_hp - get_hp(behind_target)

        print(f"  Front target damage: {front_damage}")
        print(f"  Behind wall target damage: {behind_damage}")

        assert front_damage > 0, "Front target should take damage"
        assert behind_damage > 0, \
            "Target BEHIND wall should ALSO take damage (cylinder ignores barriers)"

        print("  PASS: Cylinder AoE hits behind walls")
        return

    print("  SKIP: All attempts had nat 1/20")


# =============================================================================
# Test 7: Cylinder vs Sphere comparison (walls block Sphere but not Cylinder)
# =============================================================================
def test_cylinder_vs_sphere_wall_blocking():
    """Directly compare: a Sphere AoE IS blocked by walls, but Cylinder is NOT.

    This verifies the Cylinder's compute_objective skips shadowcast while
    Sphere's does not.
    """
    print("\n=== Test 7: Cylinder vs Sphere - wall blocking comparison ===")
    from dnd.core.aoe import Sphere, Cylinder

    reset_combat_state()
    grid = setup_arena(size=25)

    # Place a wall
    for y in range(8, 13):
        grid.set_tile(10, y, walkable=False, visible=False, name="Wall")

    # Position behind wall
    behind_pos = (11, 10)
    center = (9, 10)

    # Sphere centered at (9, 10) radius 20ft (4 tiles)
    sphere = Sphere(
        source_entity_uuid=uuid4(),
        target=center,
        radius_feet=20
    )
    sphere.compute_objective(caster_pos=center)
    sphere_hits_behind = behind_pos in sphere.affected_positions

    # Cylinder centered at same position, same radius
    cylinder = Cylinder(
        source_entity_uuid=uuid4(),
        target=center,
        radius_feet=20,
        height_feet=40
    )
    cylinder.compute_objective(caster_pos=center)
    cylinder_hits_behind = behind_pos in cylinder.affected_positions

    print(f"  Sphere hits behind wall: {sphere_hits_behind}")
    print(f"  Cylinder hits behind wall: {cylinder_hits_behind}")

    assert not sphere_hits_behind, "Sphere SHOULD be blocked by wall"
    assert cylinder_hits_behind, "Cylinder should NOT be blocked by wall (comes from above)"

    print("  PASS: Sphere blocked by wall, Cylinder not")


# =============================================================================
# Test 8: Multiple targets all take damage
# =============================================================================
def test_ice_storm_multiple_targets():
    """Multiple creatures in the cylinder all take damage."""
    print("\n=== Test 8: Ice Storm multiple targets ===")

    for attempt in range(10):
        reset_combat_state()
        setup_arena()

        caster = create_sorcerer(name="Wizard", position=(2, 10), level=5, faction="heroes")
        g1 = create_goblin(name="Goblin1", position=(10, 10), faction="monsters")
        g2 = create_goblin(name="Goblin2", position=(11, 10), faction="monsters")
        g3 = create_goblin(name="Goblin3", position=(10, 11), faction="monsters")
        Entity.update_all_entities_senses(max_distance=15)

        for g in [g1, g2, g3]:
            force_save_fail(g)
            set_hp(g, 200)

        hps_before = [get_hp(g) for g in [g1, g2, g3]]

        spell = IceStorm(
            source_entity_uuid=caster.uuid,
            end_position=(10, 10),
            cast_at_level=4,
            template=False,
            costs=IceStorm(source_entity_uuid=caster.uuid)._get_costs_for_level(4)
        )
        result = spell.apply()

        if had_critical_d20():
            print(f"  Attempt {attempt+1}: nat 1/20, retrying...")
            continue

        assert result is not None and not result.canceled, f"Should succeed: {result}"

        damages = [hps_before[i] - get_hp(g) for i, g in enumerate([g1, g2, g3])]
        print(f"  Damages: {damages}")

        for i, dmg in enumerate(damages):
            assert dmg > 0, f"Goblin{i+1} should take damage, got {dmg}"

        print("  PASS: All targets in cylinder take damage")
        return

    print("  SKIP: All attempts had nat 1/20")


# =============================================================================
# Test 9: Difficult terrain increases movement cost, then removal restores it
# =============================================================================
def test_ice_storm_terrain_movement_cost():
    """Verify that Ice Storm terrain actually increases walking cost on tiles,
    and that removal properly restores it."""
    print("\n=== Test 9: Difficult terrain movement cost and removal ===")
    reset_combat_state()
    grid = setup_arena()

    caster = create_sorcerer(name="Wizard", position=(2, 10), level=5, faction="heroes")
    mover = create_goblin(name="Mover", position=(15, 10), faction="monsters")
    Entity.update_all_entities_senses(max_distance=15)

    # Check base walking cost of a tile in the target area
    center = (10, 10)
    tile_in_zone = grid.get_tile(10, 10)
    assert tile_in_zone is not None
    cost_before = tile_in_zone.walking_cost.normalized_score
    print(f"  Walking cost before: {cost_before}")
    assert cost_before == 1, f"Base walking cost should be 1, got {cost_before}"

    set_hp(mover, 200)

    spell = IceStorm(
        source_entity_uuid=caster.uuid,
        end_position=center,
        cast_at_level=4,
        template=False,
        costs=IceStorm(source_entity_uuid=caster.uuid)._get_costs_for_level(4)
    )
    spell.apply()

    # Verify walking cost increased (difficult terrain = +1)
    cost_during = tile_in_zone.walking_cost.normalized_score
    print(f"  Walking cost during terrain: {cost_during}")
    assert cost_during == 2, f"Difficult terrain should double cost to 2, got {cost_during}"

    # Check nearby tile also affected
    adj_tile = grid.get_tile(11, 10)
    if adj_tile:
        adj_cost = adj_tile.walking_cost.normalized_score
        print(f"  Adjacent tile (11,10) cost: {adj_cost}")
        assert adj_cost == 2, f"Adjacent tile should also cost 2, got {adj_cost}"

    # Advance duration to expire terrain
    caster.advance_duration("Ice Storm Terrain")

    # Verify walking cost restored
    cost_after = tile_in_zone.walking_cost.normalized_score
    print(f"  Walking cost after expiry: {cost_after}")
    assert cost_after == 1, f"Walking cost should restore to 1 after terrain expires, got {cost_after}"

    # Adjacent tile also restored
    if adj_tile:
        adj_cost_after = adj_tile.walking_cost.normalized_score
        print(f"  Adjacent tile cost after expiry: {adj_cost_after}")
        assert adj_cost_after == 1, f"Adjacent tile cost should restore, got {adj_cost_after}"

    print("  PASS: Difficult terrain movement cost and cleanup works")


# =============================================================================
# Test 10: Mover path costs increase with difficult terrain
# =============================================================================
def test_ice_storm_terrain_affects_pathing():
    """Verify the reactive path pipeline: Ice Storm terrain sets _paths_dirty,
    and get_available_actions() triggers lazy Dijkstra recompute with new costs.

    Pipeline: ZoneControlCondition._apply_terrain_modifiers() fires SPATIAL_TILE_CHANGED
    with SensesUpdateHint(requires_paths=True) → SpatialSensesCallback._apply_hint()
    sets senses._paths_dirty=True → get_available_actions() checks _paths_dirty and
    calls update_entity_senses() → Dijkstra runs with new walking costs.
    """
    print("\n=== Test 10: Terrain affects pathing (reactive _paths_dirty pipeline) ===")
    reset_combat_state()
    grid = setup_arena(size=25)

    # Narrow corridor so mover MUST traverse the zone (no going around).
    for x in range(0, 20):
        grid.set_tile(x, 9, walkable=False, visible=False, name="Wall")
        grid.set_tile(x, 11, walkable=False, visible=False, name="Wall")

    caster = create_sorcerer(name="Wizard", position=(0, 10), level=5, faction="heroes")
    # Goblin has 30ft = 6 tiles of movement.
    mover = create_goblin(name="Mover", position=(5, 10), faction="monsters")
    Entity.update_all_entities_senses(max_distance=20)

    set_hp(mover, 200)

    # Verify _paths_dirty is False before spell
    assert not mover.senses._paths_dirty, "_paths_dirty should be False before spell"

    # Get Move targets BEFORE ice (budget-filtered by get_available_actions)
    actions_before = mover.get_available_actions()
    move_info_before = [a for a in actions_before.position_actions if a.template_name == "Move"]
    assert len(move_info_before) == 1, "Should have Move action"
    move_targets_before = {t.position for t in move_info_before[0].valid_targets}
    dest = (11, 10)  # 6 tiles away = 30ft = exact budget
    assert dest in move_targets_before, f"{dest} should be a valid Move target before ice"
    print(f"  Move targets before ice: {len(move_targets_before)}")

    # Cast ice storm at (9, 10) — creates difficult terrain in the corridor.
    spell = IceStorm(
        source_entity_uuid=caster.uuid,
        end_position=(9, 10),
        cast_at_level=4,
        template=False,
        costs=IceStorm(source_entity_uuid=caster.uuid)._get_costs_for_level(4)
    )
    spell.apply()

    # REACTIVE CHECK 1: _paths_dirty should now be True (set by callback)
    assert mover.senses._paths_dirty, \
        "_paths_dirty should be True after terrain change (reactive SPATIAL_TILE_CHANGED)"
    print(f"  _paths_dirty after spell: {mover.senses._paths_dirty}")

    # Verify tile costs changed reactively (no senses update needed)
    zone_tile = grid.get_tile(9, 10)
    assert zone_tile is not None
    cost = zone_tile.walking_cost.normalized_score
    print(f"  Tile (9,10) walking cost: {cost}")
    assert cost == 2, f"Should be difficult terrain (cost 2), got {cost}"

    # REACTIVE CHECK 2: get_available_actions() triggers lazy Dijkstra recompute
    # (entity.py:2737 checks _paths_dirty → calls update_entity_senses())
    actions_after = mover.get_available_actions()
    assert not mover.senses._paths_dirty, \
        "_paths_dirty should be cleared after get_available_actions()"

    # Move targets should be FEWER — difficult terrain eats movement budget.
    move_info_after = [a for a in actions_after.position_actions if a.template_name == "Move"]
    assert len(move_info_after) == 1
    move_targets_after = {t.position for t in move_info_after[0].valid_targets}
    print(f"  Move targets after ice: {len(move_targets_after)}")
    assert len(move_targets_after) < len(move_targets_before), \
        f"Should have fewer Move targets with difficult terrain: before={len(move_targets_before)}, after={len(move_targets_after)}"

    # (11,10) should no longer be reachable (6 tiles through cost-2 terrain = 60ft > 30ft budget)
    assert dest not in move_targets_after, \
        f"{dest} should NOT be a valid Move target through difficult terrain"

    # Verify terrain expiry restores paths
    caster.advance_duration("Ice Storm Terrain")
    assert not has_condition(caster, "Ice Storm Terrain"), "Terrain should expire"

    # _paths_dirty should be set again by terrain removal
    assert mover.senses._paths_dirty, \
        "_paths_dirty should be True after terrain removal"

    # get_available_actions() triggers lazy recompute again
    actions_restored = mover.get_available_actions()
    move_info_restored = [a for a in actions_restored.position_actions if a.template_name == "Move"]
    move_targets_restored = {t.position for t in move_info_restored[0].valid_targets}
    print(f"  Move targets after terrain expires: {len(move_targets_restored)}")
    assert dest in move_targets_restored, \
        f"{dest} should be reachable again after terrain expires"
    assert len(move_targets_restored) == len(move_targets_before), \
        f"Should restore original Move targets: before={len(move_targets_before)}, restored={len(move_targets_restored)}"

    print("  PASS: Reactive _paths_dirty pipeline works for terrain")


# =============================================================================
# Run all tests
# =============================================================================
if __name__ == "__main__":
    tests = [
        test_ice_storm_failed_save,
        test_ice_storm_passed_save,
        test_ice_storm_upcast,
        test_ice_storm_difficult_terrain,
        test_ice_storm_not_concentration,
        test_cylinder_ignores_walls,
        test_cylinder_vs_sphere_wall_blocking,
        test_ice_storm_multiple_targets,
        test_ice_storm_terrain_movement_cost,
        test_ice_storm_terrain_affects_pathing,
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
    print("All Ice Storm tests passed!")
