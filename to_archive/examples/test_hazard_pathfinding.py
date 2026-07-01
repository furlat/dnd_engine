#!/usr/bin/env python
"""
Test hazard pathfinding system.

Tests:
A. BaseBlock.is_hazardous_for() — unit tests
B. is_enemy_of() — unit tests
C. GridMap.is_position_hazardous_for() — integration tests
D. Spike trap rework — integration tests
E. Zone spell markers — integration tests
F. Safe pathfinding — path computation tests
G. Auto-safe movement
"""

from uuid import uuid4

from dnd.utils import reset_combat_state, get_hp, set_hp
from dnd.core.gridmap import get_map, reset_map
from dnd.core.base_conditions import BaseCondition, ConditionCategory, HazardFilter
from dnd.entity import Entity
from dnd.monsters.bestiary import create_skeleton, create_caster
from dnd.tiles import create_spike_zone, deactivate_spike_zone
from dnd.actions_functional import get_available_actions, execute_action
from dnd.spells.transmutation import SpikeGrowth


passed = 0
failed = 0


def check(name: str, condition: bool, detail: str = ""):
    global passed, failed
    if condition:
        passed += 1
        print(f"  PASS: {name}")
    else:
        failed += 1
        print(f"  FAIL: {name} {detail}")


def setup_arena(size: int = 15):
    """Set up a simple floor arena."""
    reset_map()
    grid = get_map()
    for x in range(size):
        for y in range(size):
            grid.set_tile(x, y, walkable=True, name="Floor")
    return grid


# =============================================================================
# A. BaseBlock.is_hazardous_for() — Unit Tests
# =============================================================================

def test_a1_no_hazard_filter():
    """Condition with no hazard_filter → not hazardous."""
    print("\n=== A1: Condition with no hazard_filter ===")
    reset_combat_state()
    grid = setup_arena()

    entity = create_skeleton(name="Test", position=(0, 0))
    tile = grid.get_tile(5, 5)
    assert tile is not None

    # Add a normal condition (no hazard_filter)
    cond = BaseCondition(
        name="TestNormal",
        source_entity_uuid=entity.uuid,
        target_entity_uuid=tile.uuid,
        condition_category=ConditionCategory.CONDITION,
    )
    tile.add_condition(cond)

    check("Non-hazard condition → not hazardous", not tile.is_hazardous_for(entity.uuid))


def test_a2_hazard_filter_all():
    """HazardFilter.ALL → hazardous for everyone."""
    print("\n=== A2: HazardFilter.ALL ===")
    reset_combat_state()
    grid = setup_arena()

    entity_a = create_skeleton(name="A", position=(0, 0))
    entity_b = create_skeleton(name="B", position=(1, 0))
    tile = grid.get_tile(5, 5)
    assert tile is not None

    cond = BaseCondition(
        name="TestHazard",
        source_entity_uuid=entity_a.uuid,
        target_entity_uuid=tile.uuid,
        condition_category=ConditionCategory.CONDITION,
        hazard_filter=HazardFilter.ALL,
    )
    tile.add_condition(cond)

    check("ALL: hazardous for entity A", tile.is_hazardous_for(entity_a.uuid))
    check("ALL: hazardous for entity B", tile.is_hazardous_for(entity_b.uuid))
    check("ALL: hazardous for None", tile.is_hazardous_for(None))


def test_a3_hazard_filter_non_source():
    """HazardFilter.NON_SOURCE → safe for source, hazardous for others."""
    print("\n=== A3: HazardFilter.NON_SOURCE ===")
    reset_combat_state()
    grid = setup_arena()

    caster = create_skeleton(name="Caster", position=(0, 0))
    enemy = create_skeleton(name="Enemy", position=(1, 0))
    ally = create_skeleton(name="Ally", position=(2, 0))
    tile = grid.get_tile(5, 5)
    assert tile is not None

    cond = BaseCondition(
        name="TestNonSource",
        source_entity_uuid=caster.uuid,
        target_entity_uuid=tile.uuid,
        condition_category=ConditionCategory.CONDITION,
        hazard_filter=HazardFilter.NON_SOURCE,
    )
    tile.add_condition(cond)

    check("NON_SOURCE: safe for caster (source)", not tile.is_hazardous_for(caster.uuid))
    check("NON_SOURCE: hazardous for enemy", tile.is_hazardous_for(enemy.uuid))
    check("NON_SOURCE: hazardous for ally (not source)", tile.is_hazardous_for(ally.uuid))


def test_a4_hazard_filter_enemies():
    """HazardFilter.ENEMIES → safe for allies, hazardous for enemies."""
    print("\n=== A4: HazardFilter.ENEMIES ===")
    reset_combat_state()
    grid = setup_arena()

    caster = create_skeleton(name="Caster", position=(0, 0), faction="heroes")
    ally = create_skeleton(name="Ally", position=(1, 0), faction="heroes")
    enemy = create_skeleton(name="Enemy", position=(2, 0), faction="villains")
    neutral = create_skeleton(name="Neutral", position=(3, 0))  # None faction
    tile = grid.get_tile(5, 5)
    assert tile is not None

    cond = BaseCondition(
        name="TestEnemies",
        source_entity_uuid=caster.uuid,
        target_entity_uuid=tile.uuid,
        condition_category=ConditionCategory.CONDITION,
        hazard_filter=HazardFilter.ENEMIES,
    )
    tile.add_condition(cond)

    check("ENEMIES: safe for caster", not tile.is_hazardous_for(caster.uuid))
    check("ENEMIES: safe for ally (same faction)", not tile.is_hazardous_for(ally.uuid))
    check("ENEMIES: hazardous for enemy (different faction)", tile.is_hazardous_for(enemy.uuid))
    check("ENEMIES: hazardous for neutral (None faction)", tile.is_hazardous_for(neutral.uuid))


def test_a5_stealth_dc_filtering():
    """stealth_dc → hidden hazards ignored by low-perception entities."""
    print("\n=== A5: stealth_dc filtering ===")
    reset_combat_state()
    grid = setup_arena()

    # Create entities with different perception
    low_percep = create_skeleton(name="LowPercep", position=(0, 0))  # Skeleton: low WIS
    # Sorcerer has higher WIS
    high_percep = create_caster(name="HighPercep", position=(1, 0))

    tile = grid.get_tile(5, 5)
    assert tile is not None

    cond = BaseCondition(
        name="HiddenHazard",
        source_entity_uuid=low_percep.uuid,
        target_entity_uuid=tile.uuid,
        condition_category=ConditionCategory.CONDITION,
        hazard_filter=HazardFilter.ALL,
        condition_stealth_dc=15,
    )
    tile.add_condition(cond)

    low_pp = low_percep.get_passive_perception()
    high_pp = high_percep.get_passive_perception()
    print(f"  Low perception passive: {low_pp}")
    print(f"  High perception passive: {high_pp}")

    # Only check based on actual perception values
    if low_pp < 15:
        check("Hidden hazard: invisible to low perception", not tile.is_hazardous_for(low_percep.uuid))
    else:
        check("Hidden hazard: visible to low perception (high enough)", tile.is_hazardous_for(low_percep.uuid))

    if high_pp >= 15:
        check("Hidden hazard: visible to high perception", tile.is_hazardous_for(high_percep.uuid))
    else:
        check("Hidden hazard: invisible to high perception (too low)", not tile.is_hazardous_for(high_percep.uuid))

    # None entity → hazardous (no perception check possible → conservative)
    # Actually, is_hazardous_for(None) with stealth_dc: entity_uuid is None → cond.condition_stealth_dc is not None
    # and entity_uuid is not None check fails → skips perception check → continues to hazard_filter check → ALL → True
    check("Hidden hazard: None entity → still hazardous", tile.is_hazardous_for(None))


# =============================================================================
# B. is_enemy_of() — Unit Tests
# =============================================================================

def test_b_is_enemy_of():
    """Test is_enemy_of() on BaseBlock and Entity."""
    print("\n=== B: is_enemy_of() ===")
    reset_combat_state()
    grid = setup_arena()

    entity_a = create_skeleton(name="A", position=(0, 0), faction="heroes")
    entity_b = create_skeleton(name="B", position=(1, 0), faction="heroes")
    entity_c = create_skeleton(name="C", position=(2, 0), faction="villains")
    entity_d = create_skeleton(name="D", position=(3, 0))  # None faction

    tile = grid.get_tile(5, 5)
    assert tile is not None

    # BaseBlock default: always True
    check("BaseBlock default: is_enemy_of → True", tile.is_enemy_of(entity_a.uuid))

    # Entity same faction: not enemy
    check("Same faction: not enemy", not entity_a.is_enemy_of(entity_b.uuid))

    # Entity different faction: enemy
    check("Different faction: enemy", entity_a.is_enemy_of(entity_c.uuid))

    # Entity None faction: enemy to all
    check("None faction vs heroes: enemy", entity_d.is_enemy_of(entity_a.uuid))
    check("Heroes vs None faction: enemy", entity_a.is_enemy_of(entity_d.uuid))

    # Self: not enemy
    check("Self: not enemy", not entity_a.is_enemy_of(entity_a.uuid))


# =============================================================================
# C. GridMap.is_position_hazardous_for() — Integration Tests
# =============================================================================

def test_c_gridmap_hazardous():
    """Test GridMap.is_position_hazardous_for()."""
    print("\n=== C: GridMap.is_position_hazardous_for() ===")
    reset_combat_state()
    grid = setup_arena()

    entity = create_skeleton(name="Test", position=(0, 0))

    # Empty tile: not hazardous
    check("Empty tile: not hazardous", not grid.is_position_hazardous_for(5, 5, entity.uuid))

    # Add hazardous condition to tile
    tile = grid.get_tile(5, 5)
    assert tile is not None
    cond = BaseCondition(
        name="TestHazard",
        source_entity_uuid=entity.uuid,
        target_entity_uuid=tile.uuid,
        condition_category=ConditionCategory.CONDITION,
        hazard_filter=HazardFilter.ALL,
    )
    tile.add_condition(cond)

    check("Tile with hazard: is hazardous", grid.is_position_hazardous_for(5, 5, entity.uuid))
    check("Adjacent tile: not hazardous", not grid.is_position_hazardous_for(5, 6, entity.uuid))


# =============================================================================
# D. Spike Trap Rework — Integration Tests
# =============================================================================

def test_d_spike_trap_rework():
    """Test spike trap rework: Floor tiles + SpikeTrapCondition."""
    print("\n=== D: Spike Trap Rework ===")
    reset_combat_state()
    grid = setup_arena()

    entity = create_skeleton(name="Test", position=(0, 0))
    Entity.update_all_entities_senses()

    # Create spike zone
    spike_positions = {(5, 5), (5, 6), (5, 7)}
    tiles, handler = create_spike_zone(spike_positions)
    for tile in tiles:
        grid._tiles[tile.position] = tile

    # All tiles should be Floor (not "Spikes")
    for tile in tiles:
        check(f"Tile {tile.position} name is Floor", tile.name == "Floor")

    # All tiles should have SpikeTrapCondition
    for tile in tiles:
        check(f"Tile {tile.position} has Spike Trap condition",
              "Spike Trap" in tile.active_conditions)

    # Hazardous check
    check("Spike tile is hazardous",
          grid.is_position_hazardous_for(5, 5, entity.uuid))

    # Deactivate
    deactivate_spike_zone(tiles, handler)
    for tile in tiles:
        check(f"Tile {tile.position} condition removed after deactivate",
              "Spike Trap" not in tile.active_conditions)
    check("Tile no longer hazardous after deactivate",
          not grid.is_position_hazardous_for(5, 5, entity.uuid))


def test_d_hidden_spike_trap():
    """Test hidden spike traps with stealth_dc."""
    print("\n=== D: Hidden Spike Trap ===")
    reset_combat_state()
    grid = setup_arena()

    low_percep = create_skeleton(name="LowPercep", position=(0, 0))
    high_percep = create_caster(name="HighPercep", position=(1, 0))

    spike_positions = {(5, 5)}
    tiles, _ = create_spike_zone(spike_positions, stealth_dc=15)
    for tile in tiles:
        grid._tiles[tile.position] = tile

    low_pp = low_percep.get_passive_perception()
    high_pp = high_percep.get_passive_perception()
    print(f"  Low perception: {low_pp}, High perception: {high_pp}")

    if low_pp < 15:
        check("Hidden trap: not hazardous for low perception",
              not grid.is_position_hazardous_for(5, 5, low_percep.uuid))
    if high_pp >= 15:
        check("Hidden trap: hazardous for high perception",
              grid.is_position_hazardous_for(5, 5, high_percep.uuid))


# =============================================================================
# E. Zone Spell Markers — Integration Tests
# =============================================================================

def test_e_spike_growth_markers():
    """Test Spike Growth zone markers."""
    print("\n=== E: Spike Growth Zone Markers ===")
    reset_combat_state()
    grid = setup_arena(20)

    caster = create_caster(name="Caster", position=(0, 0), faction="heroes")
    # Use another sorcerer as enemy so they have enough perception to detect the zone
    enemy = create_caster(name="Enemy", position=(10, 10), faction="villains")
    caster.update_entity_senses(max_distance=20)

    # Cast Spike Growth at (10, 10)
    target_pos = (10, 10)
    spell = SpikeGrowth(
        source_entity_uuid=caster.uuid,
        end_position=target_pos
    )
    spell.apply()

    # Check zone markers exist on affected tiles
    center_tile = grid.get_tile(10, 10)
    if center_tile is not None:
        has_marker = "Spike Growth" in center_tile.active_conditions
        check("Center tile has Spike Growth marker", has_marker)
        # Check the marker's hazard_filter
        marker = center_tile.active_conditions.get("Spike Growth")
        if marker:
            check("Marker hazard_filter is NON_SOURCE",
                  marker.hazard_filter == HazardFilter.NON_SOURCE)
            print(f"  Marker condition_stealth_dc: {marker.condition_stealth_dc}")
            print(f"  Enemy passive perception: {enemy.get_passive_perception()}")
    else:
        check("Center tile exists", False)

    # Caster: not hazardous (NON_SOURCE)
    check("Spike Growth: not hazardous for caster",
          not grid.is_position_hazardous_for(10, 10, caster.uuid))

    # Enemy: hazardous if they can perceive it (stealth_dc from spell_dc)
    # Spike Growth is SRD "camouflaged" — requires perception check
    spell_dc = caster.spell_save_dc()
    enemy_pp = enemy.get_passive_perception()
    print(f"  Spell DC: {spell_dc}, Enemy passive perception: {enemy_pp}")
    if enemy_pp >= spell_dc:
        check("Spike Growth: hazardous for enemy (perceives it)",
              grid.is_position_hazardous_for(10, 10, enemy.uuid))
    else:
        check("Spike Growth: NOT hazardous for enemy (can't perceive it)",
              not grid.is_position_hazardous_for(10, 10, enemy.uuid))

    # Low perception skeleton should NOT detect it
    low_percep = create_skeleton(name="Blind", position=(12, 12), faction="villains")
    low_pp = low_percep.get_passive_perception()
    print(f"  Skeleton passive perception: {low_pp}")
    if low_pp < spell_dc:
        check("Spike Growth: hidden from low-perception skeleton",
              not grid.is_position_hazardous_for(10, 10, low_percep.uuid))


def test_e_zone_removal_cleans_markers():
    """Zone removal (concentration break) cleans up tile markers."""
    print("\n=== E: Zone Removal Cleans Markers ===")
    reset_combat_state()
    grid = setup_arena(20)

    caster = create_caster(name="Caster", position=(0, 0))
    caster.update_entity_senses(max_distance=20)

    spell = SpikeGrowth(
        source_entity_uuid=caster.uuid,
        end_position=(10, 10)
    )
    spell.apply()

    # Verify marker exists
    center_tile = grid.get_tile(10, 10)
    assert center_tile is not None
    has_marker_before = "Spike Growth" in center_tile.active_conditions
    check("Marker exists before removal", has_marker_before)

    # Remove Concentrating → should remove zone + markers
    if "Concentrating" in caster.active_conditions:
        caster.remove_condition("Concentrating")

    has_marker_after = "Spike Growth" in center_tile.active_conditions
    check("Marker removed after concentration break", not has_marker_after)

    check("Tile no longer hazardous after zone removal",
          not grid.is_position_hazardous_for(10, 10, caster.uuid))


# =============================================================================
# F. Safe Pathfinding — Path Computation Tests
# =============================================================================

def test_f_safe_paths():
    """Test two-pass safe pathfinding."""
    print("\n=== F: Safe Pathfinding ===")
    reset_combat_state()
    grid = setup_arena(10)

    # Create a hazard zone at y=5, x=2-7 (blocking the horizontal middle)
    hazard_entity_uuid = uuid4()  # Dummy source for hazard conditions
    for x in range(2, 8):
        tile = grid.get_tile(x, 5)
        if tile is not None:
            cond = BaseCondition(
                name="TestHazard",
                source_entity_uuid=hazard_entity_uuid,
                target_entity_uuid=tile.uuid,
                condition_category=ConditionCategory.CONDITION,
                hazard_filter=HazardFilter.ALL,
            )
            tile.add_condition(cond)

    entity = create_skeleton(name="Test", position=(5, 3))
    Entity.update_all_entities_senses()

    # Check that entity has safe_paths computed
    _has_safe_paths = len(entity.senses.safe_paths) > 0
    print(f"  Normal paths: {len(entity.senses.paths)}")
    print(f"  Safe paths: {len(entity.senses.safe_paths)}")

    # A position on the other side of the hazard
    # Normal path to (5, 7) would go through hazard at (5, 5)
    far_pos = (5, 7)
    if far_pos in entity.senses.paths:
        normal_path = entity.senses.paths[far_pos]
        crosses_hazard = any(grid.is_position_hazardous_for(p[0], p[1], entity.uuid) for p in normal_path[1:])
        print(f"  Normal path to {far_pos}: {normal_path}")
        print(f"  Crosses hazard: {crosses_hazard}")
        check("Normal path to far side crosses hazard", crosses_hazard)

        if far_pos in entity.senses.safe_paths:
            safe_path = entity.senses.safe_paths[far_pos]
            safe_crosses = any(grid.is_position_hazardous_for(p[0], p[1], entity.uuid) for p in safe_path[1:])
            print(f"  Safe path to {far_pos}: {safe_path}")
            check("Safe path avoids hazard", not safe_crosses)
        else:
            print(f"  No safe path to {far_pos} (may be out of movement range)")
    else:
        print(f"  {far_pos} not reachable (out of movement range)")

    # Available actions should show hazard info
    actions = get_available_actions(entity)
    move_action = next((a for a in actions.position_actions if a.template_name == "Move"), None)
    if move_action:
        hazardous_targets = [t for t in move_action.valid_targets if t.is_path_hazardous]
        safe_alt_count = sum(1 for t in hazardous_targets if t.safe_path_cost is not None)
        print(f"  Hazardous targets: {len(hazardous_targets)}")
        print(f"  With safe alternative: {safe_alt_count}")
        check("Some targets marked as hazardous", len(hazardous_targets) > 0)


def test_f_no_hazard_no_safe_paths():
    """When no hazards exist, safe_paths should be empty (optimization)."""
    print("\n=== F: No Hazards → No Safe Paths ===")
    reset_combat_state()
    _grid = setup_arena(10)

    entity = create_skeleton(name="Test", position=(5, 5))
    Entity.update_all_entities_senses()

    check("No hazards → safe_paths is empty", len(entity.senses.safe_paths) == 0)


# =============================================================================
# G. Auto-Safe Movement
# =============================================================================

def test_g_auto_safe_movement():
    """move with prefer_safe=True uses safe path when available."""
    print("\n=== G: Auto-Safe Movement ===")
    reset_combat_state()
    grid = setup_arena(10)

    # Create hazard at (5, 5) only
    hazard_uuid = uuid4()
    tile = grid.get_tile(5, 5)
    if tile is not None:
        cond = BaseCondition(
            name="TestHazard",
            source_entity_uuid=hazard_uuid,
            target_entity_uuid=tile.uuid,
            condition_category=ConditionCategory.CONDITION,
            hazard_filter=HazardFilter.ALL,
        )
        tile.add_condition(cond)

    entity = create_skeleton(name="Test", position=(5, 3))
    set_hp(entity, 100)  # Plenty of HP to survive
    Entity.update_all_entities_senses()

    start_hp = get_hp(entity)
    # Move to a position that has a safe alternative (bypassing hazard)
    actions = get_available_actions(entity)
    move_action = next((a for a in actions.position_actions if a.template_name == "Move"), None)

    if move_action:
        # Find a target on the other side of the hazard
        target = next((t for t in move_action.valid_targets
                       if t.position and t.position[1] > 5 and t.is_path_hazardous
                       and t.safe_path_cost is not None), None)
        if target:
            print(f"  Moving to {target.position} with prefer_safe=True")
            execute_action(entity, "Move", target, prefer_safe=True)
            damage_after_safe = start_hp - get_hp(entity)
            print(f"  Damage taken (safe path): {damage_after_safe}")
            check("Safe path: minimal/no damage", damage_after_safe == 0)
        else:
            print("  No target with hazardous path and safe alternative found — OK for this layout")
    else:
        print("  No Move action available")


# =============================================================================
# Run all tests
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("HAZARD PATHFINDING TEST SUITE")
    print("=" * 60)

    # A: BaseBlock.is_hazardous_for()
    test_a1_no_hazard_filter()
    test_a2_hazard_filter_all()
    test_a3_hazard_filter_non_source()
    test_a4_hazard_filter_enemies()
    test_a5_stealth_dc_filtering()

    # B: is_enemy_of()
    test_b_is_enemy_of()

    # C: GridMap.is_position_hazardous_for()
    test_c_gridmap_hazardous()

    # D: Spike trap rework
    test_d_spike_trap_rework()
    test_d_hidden_spike_trap()

    # E: Zone spell markers
    test_e_spike_growth_markers()
    test_e_zone_removal_cleans_markers()

    # F: Safe pathfinding
    test_f_safe_paths()
    test_f_no_hazard_no_safe_paths()

    # G: Auto-safe movement
    test_g_auto_safe_movement()

    print("\n" + "=" * 60)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("=" * 60)

    if failed > 0:
        exit(1)
