"""
Comprehensive tests for the terrain/movement system.

Tests:
1. Movement mode pathfinding (walking, flying, swimming)
2. Diagonal border interactions
3. TileEffectCondition (difficult terrain, entry damage, turn start damage)
4. ZoneControlCondition (zone creation, cleanup, movement)
5. Zone + Concentration integration
6. Multi-step movement damage

Related test files:
- test_difficult_terrain.py: Basic tile costs and pathfinding
- test_reactive_senses.py: Movement events and step handlers
- spatial_events_test.py: GridMap basics and spatial events
"""

from typing import Type
from uuid import uuid4

from dnd.core.gridmap import get_map, reset_map
from dnd.core.base_tiles import (
    floor_factory, wall_factory, water_factory,
    difficult_terrain_factory, MovementMode
)
from dnd.core.modifiers import NumericalModifier, DamageType
from dnd.entity import Entity
from dnd.utils import reset_combat_state, setup_combat_arena
from dnd.monsters.bestiary import create_skeleton
from dnd.tile_conditions import TileEffectCondition, ZoneControlCondition


# =============================================================================
# GROUP 1: Movement Mode Pathfinding Tests
# =============================================================================

def test_flying_pathfinding_ignores_difficult_terrain():
    """Flying cost=1 on difficult terrain (walking=2)."""
    print("=" * 60)
    print("TEST: Flying Pathfinding Ignores Difficult Terrain")
    print("=" * 60)

    reset_map()
    grid = get_map()

    # Create a corridor with difficult terrain in the middle
    # [S][.][D][.][E]
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

    # Compute paths for both modes
    distances_walking, _ = grid.compute_paths((0, 0), movement_mode=MovementMode.WALKING)
    distances_flying, _ = grid.compute_paths((0, 0), movement_mode=MovementMode.FLYING)

    print(f"Walking cost to (4,0): {distances_walking.get((4, 0))}")
    print(f"Flying cost to (4,0): {distances_flying.get((4, 0))}")

    # Walking: 1 + 2 + 1 + 1 = 5
    # Flying: 1 + 1 + 1 + 1 = 4 (ignores difficult terrain)
    assert distances_walking.get((4, 0)) == 5, f"Walking should cost 5, got {distances_walking.get((4, 0))}"
    assert distances_flying.get((4, 0)) == 4, f"Flying should cost 4, got {distances_flying.get((4, 0))}"

    print("\n[PASS] Flying correctly ignores difficult terrain!")


def test_flying_pathfinding_blocked_by_walls():
    """wall_factory sets flying_cost=0 (impassable)."""
    print("\n" + "=" * 60)
    print("TEST: Flying Blocked by Walls")
    print("=" * 60)

    reset_map()
    grid = get_map()

    # Create corridor with wall in middle
    # [S][W][E]
    grid.set_tile(0, 0, walkable=True, name="Floor")
    tile_wall = wall_factory((1, 0))
    grid._tiles[(1, 0)] = tile_wall  # Replace with wall
    grid.set_tile(2, 0, walkable=True, name="Floor")

    print(f"Wall flying cost: {tile_wall.get_movement_cost(MovementMode.FLYING)}")
    assert tile_wall.get_movement_cost(MovementMode.FLYING) == 0, "Wall should block flying"

    # Compute flying paths from start
    distances_flying, _ = grid.compute_paths((0, 0), movement_mode=MovementMode.FLYING)

    print(f"Flying reachable: {sorted(distances_flying.keys())}")

    # Cannot fly through wall
    assert (2, 0) not in distances_flying, "Should not reach (2,0) through wall while flying"

    print("\n[PASS] Flying correctly blocked by walls!")


def test_swimming_pathfinding_through_water():
    """water_factory allows swimming (cost=1)."""
    print("\n" + "=" * 60)
    print("TEST: Swimming Through Water")
    print("=" * 60)

    reset_map()
    grid = get_map()

    # Create corridor with water in middle
    # [S][~][E]
    grid.set_tile(0, 0, walkable=True, name="Floor")
    tile_water = water_factory((1, 0))
    grid._tiles[(1, 0)] = tile_water
    grid.set_tile(2, 0, walkable=True, name="Floor")

    print(f"Water swimming cost: {tile_water.get_movement_cost(MovementMode.SWIMMING)}")
    assert tile_water.get_movement_cost(MovementMode.SWIMMING) == 1, "Water should allow swimming"

    # Swimming from water tile should reach floor (if floor allowed swimming)
    # Note: Floor has swimming_cost=0 by default, so swimmer is stuck
    distances_swimming, _ = grid.compute_paths((1, 0), movement_mode=MovementMode.SWIMMING)

    print(f"Swimming from water - reachable: {sorted(distances_swimming.keys())}")

    # Can only stay in water
    assert (1, 0) in distances_swimming, "Should be able to stay in water"

    print("\n[PASS] Swimming works in water!")


def test_swimming_blocked_on_land():
    """Floor has swimming_cost=0 (no water)."""
    print("\n" + "=" * 60)
    print("TEST: Swimming Blocked on Land")
    print("=" * 60)

    reset_map()
    grid = get_map()

    # Create floor tile
    floor = floor_factory((0, 0))
    grid._tiles[(0, 0)] = floor

    print(f"Floor swimming cost: {floor.get_movement_cost(MovementMode.SWIMMING)}")
    assert floor.get_movement_cost(MovementMode.SWIMMING) == 0, "Floor should have swimming cost 0"

    # Compute swimming paths from floor
    distances_swimming, _ = grid.compute_paths((0, 0), movement_mode=MovementMode.SWIMMING)

    print(f"Swimming from land - reachable: {sorted(distances_swimming.keys())}")

    # Should only include starting position (can't go anywhere)
    assert len(distances_swimming) == 1, "Swimmer on land can't move"
    assert (0, 0) in distances_swimming, "Can stay in place"

    print("\n[PASS] Swimming correctly blocked on land!")


def test_walking_blocked_by_water():
    """Cannot walk through water."""
    print("\n" + "=" * 60)
    print("TEST: Walking Blocked by Water")
    print("=" * 60)

    reset_map()
    grid = get_map()

    # Create corridor with water in middle
    # [S][~][E]
    grid.set_tile(0, 0, walkable=True, name="Floor")
    tile_water = water_factory((1, 0))
    grid._tiles[(1, 0)] = tile_water
    grid.set_tile(2, 0, walkable=True, name="Floor")

    print(f"Water walking cost: {tile_water.get_movement_cost(MovementMode.WALKING)}")
    assert tile_water.get_movement_cost(MovementMode.WALKING) == 0, "Water should block walking"

    # Compute walking paths from start
    distances_walking, _ = grid.compute_paths((0, 0), movement_mode=MovementMode.WALKING)

    print(f"Walking reachable: {sorted(distances_walking.keys())}")

    # Cannot walk through water
    assert (2, 0) not in distances_walking, "Should not reach (2,0) through water while walking"

    print("\n[PASS] Walking correctly blocked by water!")


def test_mixed_terrain_path_cost():
    """Path: floor-floor-difficult-floor = 5 cost."""
    print("\n" + "=" * 60)
    print("TEST: Mixed Terrain Path Cost")
    print("=" * 60)

    reset_map()
    grid = get_map()

    # Create: [floor][floor][difficult][floor]
    for x in range(4):
        grid.set_tile(x, 0, walkable=True, name="Floor")

    # Make tile (2,0) difficult
    tile = grid.get_tile(2, 0)
    assert tile is not None
    tile.walking_cost.self_static.add_value_modifier(
        NumericalModifier.create(
            source_entity_uuid=tile.uuid,
            name="Difficult Terrain",
            value=1
        )
    )

    distances, _ = grid.compute_paths((0, 0), movement_mode=MovementMode.WALKING)

    print(f"Cost to (1,0): {distances.get((1, 0))}")  # 1
    print(f"Cost to (2,0): {distances.get((2, 0))}")  # 1 + 2 = 3
    print(f"Cost to (3,0): {distances.get((3, 0))}")  # 1 + 2 + 1 = 4

    assert distances.get((1, 0)) == 1, "Cost to (1,0) should be 1"
    assert distances.get((2, 0)) == 3, "Cost to (2,0) should be 3"
    assert distances.get((3, 0)) == 4, "Cost to (3,0) should be 4"

    print("\n[PASS] Mixed terrain path costs correctly calculated!")


# =============================================================================
# GROUP 2: Diagonal Border Tests
# =============================================================================

def test_diagonal_border_northeast_blocked():
    """border_north=False + border_east=False blocks NE entry."""
    print("\n" + "=" * 60)
    print("TEST: Diagonal Border NE Blocked")
    print("=" * 60)

    reset_map()
    grid = get_map()

    # Create 3x3 grid
    for x in range(3):
        for y in range(3):
            grid.set_tile(x, y, walkable=True, name="Floor")

    # Get center tile and block both north and east borders
    center = grid.get_tile(1, 1)
    assert center is not None
    center.border_north = False  # Block from y+1
    center.border_east = False   # Block from x+1

    print(f"Center tile borders: N={center.border_north}, S={center.border_south}, E={center.border_east}, W={center.border_west}")

    # Test diagonal entry from NE (position 2,2 to 1,1)
    # Coming from NE means dx=-1, dy=-1
    # This checks border_east and border_north
    can_enter = center.can_enter_from((2, 2))
    print(f"Can enter (1,1) from (2,2) [NE]: {can_enter}")

    # With both borders blocked, diagonal should be blocked
    assert can_enter == False, "Should not enter from NE when both N and E borders blocked"

    print("\n[PASS] Diagonal NE correctly blocked when both borders blocked!")


def test_diagonal_border_partial_allows():
    """border_north=False alone doesn't block NE entry."""
    print("\n" + "=" * 60)
    print("TEST: Diagonal Border Partial Allows")
    print("=" * 60)

    reset_map()
    grid = get_map()

    # Create 3x3 grid
    for x in range(3):
        for y in range(3):
            grid.set_tile(x, y, walkable=True, name="Floor")

    # Get center tile and block only north border
    center = grid.get_tile(1, 1)
    assert center is not None
    center.border_north = False  # Block from y+1

    print(f"Center tile borders: N={center.border_north}, S={center.border_south}, E={center.border_east}, W={center.border_west}")

    # Test diagonal entry from NE (position 2,2 to 1,1)
    # Diagonal requires at least ONE border open (east OR north)
    # East is still open
    can_enter = center.can_enter_from((2, 2))
    print(f"Can enter (1,1) from (2,2) [NE]: {can_enter}")

    # With only north blocked, east is open, diagonal should work
    assert can_enter == True, "Should enter from NE when east border still open"

    print("\n[PASS] Diagonal allowed with partial border blocking!")


def test_orthogonal_borders_dont_affect_diagonal():
    """North border only blocks from south, not diagonals."""
    print("\n" + "=" * 60)
    print("TEST: Orthogonal Borders Don't Affect Wrong Diagonals")
    print("=" * 60)

    reset_map()
    grid = get_map()

    # Create 3x3 grid
    for x in range(3):
        for y in range(3):
            grid.set_tile(x, y, walkable=True, name="Floor")

    # Get center tile and block north border
    center = grid.get_tile(1, 1)
    assert center is not None
    center.border_north = False  # Block from y+1 (from north)

    # Test orthogonal entry from north (blocked) and south (open)
    from_north = center.can_enter_from((1, 2))  # Coming from y+1
    from_south = center.can_enter_from((1, 0))  # Coming from y-1

    print(f"Can enter from north (1,2): {from_north}")
    print(f"Can enter from south (1,0): {from_south}")

    assert from_north == False, "Should block entry from north"
    assert from_south == True, "Should allow entry from south"

    # Test SW diagonal - should use west and south borders, not north
    from_sw = center.can_enter_from((0, 0))  # dx=1, dy=1 → uses west and south
    print(f"Can enter from SW (0,0): {from_sw}")
    assert from_sw == True, "SW diagonal should not be affected by north border"

    print("\n[PASS] Orthogonal borders correctly scoped!")


# =============================================================================
# GROUP 3: TileEffectCondition Tests
# =============================================================================

class TestDifficultTerrain(TileEffectCondition):
    """Test tile effect that adds difficult terrain."""
    name: str = "Test Difficult"
    description: str = "Test difficult terrain effect"
    adds_difficult_terrain: bool = True


class TestFireTile(TileEffectCondition):
    """Test tile effect with entry damage."""
    name: str = "Test Fire"
    description: str = "Burns entities that enter"
    damage_on_entry_dice: str = "1d6"
    damage_on_entry_type: DamageType = DamageType.FIRE


class TestSpikedFloor(TileEffectCondition):
    """Test tile effect with turn start damage."""
    name: str = "Test Spikes"
    description: str = "Damages at turn start"
    damage_on_turn_start_dice: str = "1d4"
    damage_on_turn_start_type: DamageType = DamageType.PIERCING


def test_tile_effect_adds_difficult_terrain():
    """adds_difficult_terrain=True increases walking_cost."""
    print("\n" + "=" * 60)
    print("TEST: TileEffectCondition Adds Difficult Terrain")
    print("=" * 60)

    reset_combat_state()
    grid = get_map()

    # Create a floor tile
    tile = grid.set_tile(0, 0, walkable=True, name="Floor")
    initial_cost = tile.get_movement_cost(MovementMode.WALKING)
    print(f"Initial walking cost: {initial_cost}")
    assert initial_cost == 1, "Floor should have cost 1"

    # Apply difficult terrain condition using tile.add_condition
    source_uuid = uuid4()
    effect = TestDifficultTerrain(
        source_entity_uuid=source_uuid,
        target_entity_uuid=tile.uuid
    )
    tile.add_condition(effect)

    new_cost = tile.get_movement_cost(MovementMode.WALKING)
    print(f"Walking cost after effect: {new_cost}")

    assert new_cost == 2, f"Should be 2 with difficult terrain, got {new_cost}"

    print("\n[PASS] TileEffectCondition correctly adds difficult terrain!")


def test_tile_effect_entry_damage():
    """Entry damage handler fires on SPATIAL_ENTITY_ENTERED."""
    print("\n" + "=" * 60)
    print("TEST: TileEffectCondition Entry Damage")
    print("=" * 60)

    reset_combat_state()
    grid = get_map()

    # Create tiles: [start][fire]
    grid.set_tile(0, 0, walkable=True, name="Floor")
    fire_tile = grid.set_tile(1, 0, walkable=True, name="Floor")

    # Create entity at start
    entity = create_skeleton(name="Test Entity", position=(0, 0))
    Entity.update_all_entities_senses()

    initial_hp = entity.get_hp()
    print(f"Entity HP before: {initial_hp}")

    # Apply fire effect to tile using tile.add_condition
    source_uuid = uuid4()
    effect = TestFireTile(
        source_entity_uuid=source_uuid,
        target_entity_uuid=fire_tile.uuid
    )
    fire_tile.add_condition(effect)

    # Move entity to fire tile (triggers SPATIAL_ENTITY_ENTERED)
    grid.move_entity(entity.uuid, (1, 0))

    final_hp = entity.get_hp()
    print(f"Entity HP after entering fire: {final_hp}")

    assert final_hp < initial_hp, f"Should have taken damage! HP: {initial_hp} -> {final_hp}"

    print("\n[PASS] Entry damage handler fires correctly!")


def test_tile_effect_turn_start_damage():
    """Turn start damage handler fires on TURN_START."""
    print("\n" + "=" * 60)
    print("TEST: TileEffectCondition Turn Start Damage")
    print("=" * 60)

    reset_combat_state()
    grid = get_map()

    # Create tile with spikes
    spike_tile = grid.set_tile(0, 0, walkable=True, name="Floor")

    # Create entity on the tile
    entity = create_skeleton(name="Test Entity", position=(0, 0))
    Entity.update_all_entities_senses()

    # Apply spike effect to tile
    source_uuid = uuid4()
    effect = TestSpikedFloor(
        source_entity_uuid=source_uuid,
        target_entity_uuid=spike_tile.uuid
    )
    spike_tile.add_condition(effect)

    initial_hp = entity.get_hp()
    print(f"Entity HP before turn: {initial_hp}")

    # Trigger turn start
    entity.on_turn_start()

    final_hp = entity.get_hp()
    print(f"Entity HP after turn start: {final_hp}")

    assert final_hp < initial_hp, f"Should have taken damage! HP: {initial_hp} -> {final_hp}"

    print("\n[PASS] Turn start damage handler fires correctly!")


def test_tile_effect_cleanup_on_removal():
    """Removing condition removes modifiers."""
    print("\n" + "=" * 60)
    print("TEST: TileEffectCondition Cleanup on Removal")
    print("=" * 60)

    reset_combat_state()
    grid = get_map()

    # Create a floor tile
    tile = grid.set_tile(0, 0, walkable=True, name="Floor")

    # Apply difficult terrain condition
    source_uuid = uuid4()
    effect = TestDifficultTerrain(
        source_entity_uuid=source_uuid,
        target_entity_uuid=tile.uuid
    )
    tile.add_condition(effect)

    cost_with_effect = tile.get_movement_cost(MovementMode.WALKING)
    print(f"Walking cost with effect: {cost_with_effect}")
    assert cost_with_effect == 2, "Should be difficult terrain"

    # Remove the condition
    tile.remove_condition(effect.name)

    cost_after_removal = tile.get_movement_cost(MovementMode.WALKING)
    print(f"Walking cost after removal: {cost_after_removal}")

    assert cost_after_removal == 1, f"Should be normal after removal, got {cost_after_removal}"

    print("\n[PASS] Condition cleanup works correctly!")


# =============================================================================
# GROUP 4: ZoneControlCondition Tests
# =============================================================================

class TestZoneTileEffect(TileEffectCondition):
    """Tile effect for test zone."""
    name: str = "Test Zone Effect"
    description: str = "Effect from test zone"
    adds_difficult_terrain: bool = True


class TestZoneControl(ZoneControlCondition):
    """Test zone that creates difficult terrain."""
    name: str = "Test Zone"
    description: str = "Test zone control"
    zone_shape: str = "sphere"
    zone_radius_feet: int = 10
    adds_difficult_terrain: bool = True  # Enable terrain modifiers

    def get_tile_effect_class(self) -> Type[TileEffectCondition]:
        return TestZoneTileEffect


def test_zone_control_computes_affected_positions():
    """_compute_affected_positions() uses AoE shapes correctly."""
    print("\n" + "=" * 60)
    print("TEST: ZoneControlCondition Computes Positions")
    print("=" * 60)

    reset_combat_state()
    grid = get_map()

    # Create a 10x10 grid
    for x in range(10):
        for y in range(10):
            grid.set_tile(x, y, walkable=True, name="Floor")

    # Create zone at center (5, 5) with 10ft radius (2 tiles)
    source_uuid = uuid4()
    zone = TestZoneControl(
        source_entity_uuid=source_uuid,
        target_entity_uuid=source_uuid,
        zone_center=(5, 5),
        zone_radius_feet=10
    )

    # Compute positions
    positions = zone._compute_affected_positions()

    print(f"Zone center: (5, 5)")
    print(f"Zone radius: 10ft (2 tiles)")
    print(f"Affected positions: {sorted(positions)}")
    print(f"Count: {len(positions)}")

    # Center should be included
    assert (5, 5) in positions, "Center should be affected"

    # Positions within 2 tiles should be included
    assert (6, 5) in positions, "Adjacent should be affected"
    assert (5, 6) in positions, "Adjacent should be affected"

    print("\n[PASS] Zone position computation works!")


def test_zone_control_applies_tile_effects():
    """Tile effects applied to all affected tiles."""
    print("\n" + "=" * 60)
    print("TEST: ZoneControlCondition Applies Effects")
    print("=" * 60)

    reset_combat_state()
    grid = get_map()

    # Create a 10x10 grid
    for x in range(10):
        for y in range(10):
            grid.set_tile(x, y, walkable=True, name="Floor")

    # Create entity to "own" the zone
    entity = create_skeleton(name="Zone Caster", position=(0, 0))
    Entity.update_all_entities_senses()

    # Create and apply zone at (5, 5)
    zone = TestZoneControl(
        source_entity_uuid=entity.uuid,
        target_entity_uuid=entity.uuid,
        zone_center=(5, 5),
        zone_radius_feet=10
    )
    entity.add_condition(zone)

    # Check that center tile has the effect
    center_tile = grid.get_tile(5, 5)
    assert center_tile is not None

    cost = center_tile.get_movement_cost(MovementMode.WALKING)
    print(f"Center tile walking cost: {cost}")

    assert cost == 2, f"Zone should add difficult terrain, got cost {cost}"

    print(f"Affected positions: {zone.affected_positions}")
    print(f"Terrain conditions tracked: {len(zone.terrain_conditions)}")

    print("\n[PASS] Zone correctly applies tile effects!")


def test_zone_control_cleanup_removes_all_effects():
    """Removing zone removes all tile conditions."""
    print("\n" + "=" * 60)
    print("TEST: ZoneControlCondition Cleanup")
    print("=" * 60)

    reset_combat_state()
    grid = get_map()

    # Create a 10x10 grid
    for x in range(10):
        for y in range(10):
            grid.set_tile(x, y, walkable=True, name="Floor")

    # Create entity and zone
    entity = create_skeleton(name="Zone Caster", position=(0, 0))
    Entity.update_all_entities_senses()

    zone = TestZoneControl(
        source_entity_uuid=entity.uuid,
        target_entity_uuid=entity.uuid,
        zone_center=(5, 5),
        zone_radius_feet=10
    )
    entity.add_condition(zone)

    # Verify zone is applied
    center_tile = grid.get_tile(5, 5)
    assert center_tile is not None
    assert center_tile.get_movement_cost(MovementMode.WALKING) == 2, "Zone should be active"

    print(f"Before removal - center tile cost: {center_tile.get_movement_cost(MovementMode.WALKING)}")

    # Remove the zone from entity
    entity.remove_condition(zone.name)

    # Check tile is back to normal
    cost_after = center_tile.get_movement_cost(MovementMode.WALKING)
    print(f"After removal - center tile cost: {cost_after}")

    assert cost_after == 1, f"Should be normal after zone removal, got {cost_after}"

    print("\n[PASS] Zone cleanup removes all tile effects!")


def test_zone_move_updates_affected_tiles():
    """move_zone() removes old, applies new."""
    print("\n" + "=" * 60)
    print("TEST: ZoneControlCondition Move Zone")
    print("=" * 60)

    reset_combat_state()
    grid = get_map()

    # Create a 15x15 grid
    for x in range(15):
        for y in range(15):
            grid.set_tile(x, y, walkable=True, name="Floor")

    # Create entity and zone at (5, 5)
    entity = create_skeleton(name="Zone Caster", position=(0, 0))
    Entity.update_all_entities_senses()

    zone = TestZoneControl(
        source_entity_uuid=entity.uuid,
        target_entity_uuid=entity.uuid,
        zone_center=(5, 5),
        zone_radius_feet=10
    )
    entity.add_condition(zone)

    # Verify initial position affected
    old_center = grid.get_tile(5, 5)
    assert old_center is not None
    assert old_center.get_movement_cost(MovementMode.WALKING) == 2

    print(f"Before move - (5,5) cost: {old_center.get_movement_cost(MovementMode.WALKING)}")

    # Move zone to (10, 10)
    zone.move_zone((10, 10))

    # Old center should be normal
    old_cost = old_center.get_movement_cost(MovementMode.WALKING)
    print(f"After move - (5,5) cost: {old_cost}")
    assert old_cost == 1, f"Old center should be normal, got {old_cost}"

    # New center should be difficult terrain
    new_center = grid.get_tile(10, 10)
    assert new_center is not None
    new_cost = new_center.get_movement_cost(MovementMode.WALKING)
    print(f"After move - (10,10) cost: {new_cost}")
    assert new_cost == 2, f"New center should be difficult terrain, got {new_cost}"

    print("\n[PASS] Zone movement updates tiles correctly!")


# =============================================================================
# GROUP 5: Zone + Concentration Integration
# =============================================================================

def test_concentration_break_removes_zone():
    """Breaking concentration removes zone and all tile effects."""
    print("\n" + "=" * 60)
    print("TEST: Concentration Break Removes Zone")
    print("=" * 60)

    reset_combat_state()
    grid = get_map()

    # Create grid
    for x in range(10):
        for y in range(10):
            grid.set_tile(x, y, walkable=True, name="Floor")

    # Create caster and dummy target for encounter setup
    from dnd.conditions import Concentrating
    caster = create_skeleton(name="Caster", position=(0, 0))
    target = create_skeleton(name="Target", position=(5, 0))
    _ = setup_combat_arena(caster, target)

    # Create zone
    zone = TestZoneControl(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=caster.uuid,
        zone_center=(5, 5),
        zone_radius_feet=10
    )
    caster.add_condition(zone)

    # Create concentration condition linked to zone
    concentration = Concentrating(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=caster.uuid,
        spell_name="Test Zone Spell"
    )
    caster.add_condition(concentration)

    # Link zone as external condition of concentration
    concentration.add_external_condition(caster.uuid, zone.uuid)

    # Verify zone is active
    center_tile = grid.get_tile(5, 5)
    assert center_tile is not None
    assert center_tile.get_movement_cost(MovementMode.WALKING) == 2

    print(f"Before concentration break - (5,5) cost: {center_tile.get_movement_cost(MovementMode.WALKING)}")
    print(f"Caster has Concentrating: {'Concentrating' in caster.active_conditions}")
    print(f"Caster has Test Zone: {'Test Zone' in caster.active_conditions}")

    # Break concentration
    caster.remove_condition("Concentrating")

    # Zone should be removed via external_conditions cleanup
    cost_after = center_tile.get_movement_cost(MovementMode.WALKING)
    print(f"After concentration break - (5,5) cost: {cost_after}")
    print(f"Caster has Test Zone: {'Test Zone' in caster.active_conditions}")

    assert cost_after == 1, f"Zone should be removed, tile cost should be 1, got {cost_after}"
    assert "Test Zone" not in caster.active_conditions, "Zone condition should be removed"

    print("\n[PASS] Concentration break removes zone correctly!")


# =============================================================================
# GROUP 6: Multi-Step Movement Damage (Using Encounter)
# =============================================================================

def test_entry_damage_on_each_step():
    """Moving through multiple fire tiles deals damage per tile."""
    print("\n" + "=" * 60)
    print("TEST: Entry Damage on Each Step")
    print("=" * 60)

    reset_combat_state()
    grid = get_map()

    # Create corridor: [start][fire][fire][fire][end]
    for x in range(5):
        grid.set_tile(x, 0, walkable=True, name="Floor")

    # Create entity with high HP for this test
    entity = create_skeleton(name="Test Entity", position=(0, 0))
    # Create a second entity for encounter
    dummy = create_skeleton(name="Dummy", position=(4, 0))
    _ = setup_combat_arena(entity, dummy)

    # Apply fire effect to tiles 1, 2, 3
    source_uuid = uuid4()
    for x in [1, 2, 3]:
        tile = grid.get_tile(x, 0)
        assert tile is not None

        effect = TestFireTile(
            source_entity_uuid=source_uuid,
            target_entity_uuid=tile.uuid
        )
        tile.add_condition(effect)

    initial_hp = entity.get_hp()
    print(f"Entity HP before: {initial_hp}")

    # Move through each fire tile one at a time
    damage_events = []
    for x in [1, 2, 3]:
        hp_before = entity.get_hp()
        grid.move_entity(entity.uuid, (x, 0))
        hp_after = entity.get_hp()
        damage = hp_before - hp_after
        damage_events.append(damage)
        print(f"Step to ({x}, 0): took {damage} damage")

    final_hp = entity.get_hp()
    total_damage = initial_hp - final_hp

    print(f"Total damage taken: {total_damage}")
    print(f"Damage per step: {damage_events}")

    # Should have taken damage at each step
    assert all(d > 0 for d in damage_events), "Should take damage at each fire tile"
    assert len([d for d in damage_events if d > 0]) == 3, "Should have 3 damage events"

    print("\n[PASS] Entry damage fires for each step!")


# =============================================================================
# Main
# =============================================================================

def main():
    """Run all terrain movement system tests."""
    print("\n" + "=" * 60)
    print("TERRAIN MOVEMENT SYSTEM COMPREHENSIVE TESTS")
    print("=" * 60)

    # Group 1: Movement Mode Pathfinding
    print("\n### GROUP 1: Movement Mode Pathfinding ###")
    test_flying_pathfinding_ignores_difficult_terrain()
    test_flying_pathfinding_blocked_by_walls()
    test_swimming_pathfinding_through_water()
    test_swimming_blocked_on_land()
    test_walking_blocked_by_water()
    test_mixed_terrain_path_cost()

    # Group 2: Diagonal Borders
    print("\n### GROUP 2: Diagonal Borders ###")
    test_diagonal_border_northeast_blocked()
    test_diagonal_border_partial_allows()
    test_orthogonal_borders_dont_affect_diagonal()

    # Group 3: TileEffectCondition
    print("\n### GROUP 3: TileEffectCondition ###")
    test_tile_effect_adds_difficult_terrain()
    test_tile_effect_entry_damage()
    test_tile_effect_turn_start_damage()
    test_tile_effect_cleanup_on_removal()

    # Group 4: ZoneControlCondition
    print("\n### GROUP 4: ZoneControlCondition ###")
    test_zone_control_computes_affected_positions()
    test_zone_control_applies_tile_effects()
    test_zone_control_cleanup_removes_all_effects()
    test_zone_move_updates_affected_tiles()

    # Group 5: Zone + Concentration Integration
    print("\n### GROUP 5: Zone + Concentration Integration ###")
    test_concentration_break_removes_zone()

    # Group 6: Multi-Step Movement Damage
    print("\n### GROUP 6: Multi-Step Movement Damage ###")
    test_entry_damage_on_each_step()

    print("\n" + "=" * 60)
    print("ALL TERRAIN MOVEMENT SYSTEM TESTS PASSED!")
    print("=" * 60)


if __name__ == "__main__":
    main()
