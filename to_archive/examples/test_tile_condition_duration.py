"""
Test tile condition duration via environment step in Encounter.

Tests:
1. Tile condition with ROUNDS duration expires after advance_duration calls
2. Tile condition with linked_conditions cleans up entity condition on expiry
3. Environment step in Encounter advances tile conditions at round end
"""

from dnd.utils import reset_combat_state, setup_combat_arena
from dnd.core.gridmap import get_map
from dnd.core.base_conditions import BaseCondition, Duration, DurationType
from dnd.entity import Entity
from dnd.monsters.bestiary import create_skeleton
from uuid import uuid4


class TestTileEffect(BaseCondition):
    """A simple tile condition with round-based duration for testing."""
    name: str = "TestTileEffect"
    description: str = "Test tile effect"


class TestEntityEffect(BaseCondition):
    """A simple entity condition for testing linked cleanup."""
    name: str = "TestEntityEffect"
    description: str = "Test entity effect applied by tile"


def test_tile_advance_duration():
    """Test that advance_duration on tile removes expired conditions."""
    print("=== Test 1: Tile advance_duration removes expired conditions ===")
    reset_combat_state()
    grid = get_map()

    source_id = uuid4()
    grid.set_tile(3, 3)
    tile = grid.get_tile(3, 3)
    assert tile is not None

    # Add a 2-round duration condition
    effect = TestTileEffect(
        source_entity_uuid=source_id,
        target_entity_uuid=tile.uuid,
        duration=Duration(duration=2, duration_type=DurationType.ROUNDS,
                         source_entity_uuid=source_id, target_entity_uuid=tile.uuid)
    )
    tile.add_condition(effect)
    assert "TestTileEffect" in tile.active_conditions

    # Advance once — should still be active (1 round left)
    removed = tile.advance_duration("TestTileEffect")
    assert not removed, "Should NOT be removed after 1 round"
    assert "TestTileEffect" in tile.active_conditions
    print("  After 1 advance: still active")

    # Advance again — should expire
    removed = tile.advance_duration("TestTileEffect")
    assert removed, "Should be removed after 2 rounds"
    assert "TestTileEffect" not in tile.active_conditions
    print("  After 2 advances: expired and removed")

    print("  PASSED\n")


def test_tile_expiry_cleans_linked_conditions():
    """Test that when a tile condition expires, its linked entity conditions are cleaned up."""
    print("=== Test 2: Tile condition expiry cleans linked entity conditions ===")
    reset_combat_state()
    grid = get_map()

    skeleton = create_skeleton(name="Skeleton", position=(3, 3))
    Entity.update_all_entities_senses()

    grid.set_tile(3, 3)
    tile = grid.get_tile(3, 3)
    assert tile is not None

    source_id = uuid4()

    # Add tile condition with 1-round duration
    tile_effect = TestTileEffect(
        source_entity_uuid=source_id,
        target_entity_uuid=tile.uuid,
        duration=Duration(duration=1, duration_type=DurationType.ROUNDS,
                         source_entity_uuid=source_id, target_entity_uuid=tile.uuid)
    )
    tile.add_condition(tile_effect)

    # Add entity condition linked to tile condition
    entity_effect = TestEntityEffect(
        source_entity_uuid=source_id,
        target_entity_uuid=skeleton.uuid
    )
    skeleton.add_condition(entity_effect)

    # Link: tile condition owns entity condition
    tile_effect.add_linked_condition(skeleton.uuid, entity_effect.uuid)

    assert "TestTileEffect" in tile.active_conditions
    assert "TestEntityEffect" in skeleton.active_conditions
    print("  Both conditions active")

    # Advance — tile condition expires, entity condition should be cleaned up
    removed = tile.advance_duration("TestTileEffect")
    assert removed, "Tile condition should expire"
    assert "TestTileEffect" not in tile.active_conditions
    assert "TestEntityEffect" not in skeleton.active_conditions, \
        "Entity condition should be removed via linked_conditions cleanup"
    print("  Tile condition expired → entity condition auto-cleaned")

    print("  PASSED\n")


def test_environment_step_in_encounter():
    """Test that Encounter._environment_step advances tile condition durations."""
    print("=== Test 3: Environment step advances tile conditions at round end ===")
    reset_combat_state()
    grid = get_map()

    attacker = create_skeleton(name="Attacker", position=(0, 0), faction="team_a")
    defender = create_skeleton(name="Defender", position=(1, 0), faction="team_b")
    Entity.update_all_entities_senses()

    encounter = setup_combat_arena(attacker, defender)

    # Set up a tile with a 2-round condition
    grid.set_tile(5, 5)
    tile = grid.get_tile(5, 5)
    assert tile is not None

    source_id = uuid4()
    tile_effect = TestTileEffect(
        source_entity_uuid=source_id,
        target_entity_uuid=tile.uuid,
        duration=Duration(duration=2, duration_type=DurationType.ROUNDS,
                         source_entity_uuid=source_id, target_entity_uuid=tile.uuid)
    )
    tile.add_condition(tile_effect)
    assert "TestTileEffect" in tile.active_conditions

    # Start encounter and run 2 full rounds (each round = all combatants act)
    encounter.start_encounter()

    # Round 1: both combatants act
    # start_encounter fires round_start, then we manually run turns
    encounter.start_turn()  # Turn 1
    encounter.end_turn()
    encounter.next_turn()   # Turn 2 (next_turn auto-calls start_turn)
    encounter.end_turn()
    encounter.next_turn()   # Wraps around → _advance_round → _environment_step

    # After 1 round: condition should still be active (1 round left)
    assert "TestTileEffect" in tile.active_conditions, \
        "Tile condition should survive 1 round"
    print("  After round 1: tile condition still active")

    # Round 2: both combatants act (next_turn already started first turn of round 2)
    encounter.end_turn()
    encounter.next_turn()   # Turn 2 of round 2
    encounter.end_turn()
    encounter.next_turn()   # Wraps around → _advance_round → _environment_step

    # After 2 rounds: condition should be expired
    assert "TestTileEffect" not in tile.active_conditions, \
        "Tile condition should expire after 2 rounds"
    print("  After round 2: tile condition expired")

    print("  PASSED\n")


if __name__ == "__main__":
    print("=" * 60)
    print("TILE CONDITION DURATION TESTS")
    print("=" * 60)
    test_tile_advance_duration()
    test_tile_expiry_cleans_linked_conditions()
    test_environment_step_in_encounter()
    print("=" * 60)
    print("ALL TESTS PASSED!")
    print("=" * 60)
