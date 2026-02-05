#!/usr/bin/env python
"""
Test BG3-style Prone auto-stand behavior.

Tests:
1. Prone condition applies correctly
2. At turn start, entity auto-stands (Prone removed)
3. Half movement is deducted
4. Entity can still move with remaining movement
"""

from uuid import uuid4

from dnd.utils import reset_combat_state, has_condition
from dnd.monsters.bestiary import create_skeleton
from dnd.conditions import Prone
from dnd.entity import Entity
from dnd.encounter import Encounter
from dnd.controller import PassController
from dnd.core.gridmap import get_map, reset_map


def setup_arena(size: int = 20):
    """Set up a simple floor arena for testing."""
    reset_map()
    grid = get_map()
    for x in range(size):
        for y in range(size):
            grid.set_tile(x, y, walkable=True, name="Floor")
    return grid


def test_prone_auto_stand():
    """Test that Prone auto-removes at turn start with movement cost."""
    print("=" * 60)
    print("TEST: Prone Auto-Stand (BG3 Style)")
    print("=" * 60)

    reset_combat_state()

    # Create entity
    entity = create_skeleton(name="TestEntity", position=(5, 5))
    Entity.update_all_entities_senses()

    # Verify starting state
    base_movement = entity.action_economy.get_base_value("movement")
    print(f"\n1. Initial state:")
    print(f"   Base movement: {base_movement}ft")
    print(f"   Current movement: {entity.action_economy.movement.normalized_score}ft")
    print(f"   Has Prone: {has_condition(entity, 'Prone')}")

    assert not has_condition(entity, "Prone"), "Should not start prone"
    assert entity.action_economy.movement.normalized_score == base_movement, "Should have full movement"

    # Apply Prone condition
    prone = Prone(
        source_entity_uuid=entity.uuid,
        target_entity_uuid=entity.uuid
    )
    entity.add_condition(prone)

    print(f"\n2. After applying Prone:")
    print(f"   Has Prone: {has_condition(entity, 'Prone')}")
    print(f"   Current movement: {entity.action_economy.movement.normalized_score}ft")

    assert has_condition(entity, "Prone"), "Should be prone"

    # Create encounter for turn management - single entity so it goes first
    encounter = Encounter(name="Test", source_entity_uuid=uuid4())
    controller = PassController(source_entity_uuid=entity.uuid)
    encounter.add_combatant(entity, controller)
    encounter.roll_initiative()
    encounter.start_encounter()

    # Start turn (no argument - uses current entity from turn order)
    encounter.start_turn()

    print(f"\n3. After turn start (should auto-stand):")
    print(f"   Has Prone: {has_condition(entity, 'Prone')}")
    print(f"   Current movement: {entity.action_economy.movement.normalized_score}ft")

    assert not has_condition(entity, "Prone"), "Should no longer be prone"

    # Check movement was deducted
    half_movement = base_movement // 2
    expected_remaining = base_movement - half_movement
    actual_remaining = entity.action_economy.movement.normalized_score

    print(f"\n4. Movement calculation:")
    print(f"   Base movement: {base_movement}ft")
    print(f"   Half (stand up cost): {half_movement}ft")
    print(f"   Expected remaining: {expected_remaining}ft")
    print(f"   Actual remaining: {actual_remaining}ft")

    assert actual_remaining == expected_remaining, \
        f"Movement mismatch: expected {expected_remaining}ft, got {actual_remaining}ft"

    print("\n" + "=" * 60)
    print("PASS: Prone auto-stand works correctly!")
    print("=" * 60)


def test_prone_not_auto_stand_on_other_turn():
    """Test that Prone doesn't auto-remove on other entity's turn.

    We directly call on_turn_start() which fires the TURN_START event
    through its phases.
    """
    print("\n" + "=" * 60)
    print("TEST: Prone Only Auto-Stands on Own Turn")
    print("=" * 60)

    reset_combat_state()

    # Create two entities
    entity1 = create_skeleton(name="ProneEntity", position=(0, 0))
    entity2 = create_skeleton(name="OtherEntity", position=(5, 0))
    Entity.update_all_entities_senses()

    # Apply Prone to entity1
    prone = Prone(
        source_entity_uuid=entity2.uuid,
        target_entity_uuid=entity1.uuid
    )
    entity1.add_condition(prone)

    print(f"\n1. Entity1 is prone: {has_condition(entity1, 'Prone')}")
    assert has_condition(entity1, "Prone")

    # Entity2's turn start - entity1 should remain prone
    print(f"\n2. Entity2 takes their turn:")
    entity2.on_turn_start()

    print(f"   Entity1 still prone: {has_condition(entity1, 'Prone')}")
    assert has_condition(entity1, "Prone"), "Entity1 should still be prone"

    # Entity1's turn start - entity1 should auto-stand
    print(f"\n3. Entity1 takes their turn:")
    entity1.on_turn_start()

    print(f"   Entity1 still prone: {has_condition(entity1, 'Prone')}")
    assert not has_condition(entity1, "Prone"), "Entity1 should have auto-stood"

    print("\n" + "=" * 60)
    print("PASS: Prone only auto-stands on own turn!")
    print("=" * 60)


def test_stand_up_no_longer_registered():
    """Test that StandUp action is no longer registered."""
    print("\n" + "=" * 60)
    print("TEST: StandUp Action Not Registered")
    print("=" * 60)

    reset_combat_state()

    entity = create_skeleton(name="TestEntity", position=(0, 0))
    Entity.update_all_entities_senses()

    # Check available actions
    available = entity.get_available_actions()
    action_names = [a.template_name for a in available.all_actions]

    print(f"\nRegistered actions: {action_names}")

    assert "Stand Up" not in action_names, "StandUp should not be registered"

    print("\n" + "=" * 60)
    print("PASS: StandUp action is not registered!")
    print("=" * 60)


def test_prone_during_own_turn_with_movement():
    """Test that Prone is immediately negated when applied during own turn with movement."""
    print("\n" + "=" * 60)
    print("TEST: Prone During Own Turn (Immediate Stand)")
    print("=" * 60)

    reset_combat_state()
    setup_arena()

    # Create entity
    entity = create_skeleton(name="Entity", position=(0, 0))
    entity.update_entity_senses()

    # Simulate turn start
    entity.on_turn_start()

    initial_movement = entity.action_economy.movement.normalized_score
    print(f"\n1. During own turn:")
    print(f"   Is my turn: {entity.is_my_turn}")
    print(f"   Current movement: {initial_movement}ft")

    # Apply Prone during own turn
    print(f"\n2. Applying Prone during own turn...")
    from dnd.conditions import Prone
    prone = Prone(
        source_entity_uuid=entity.uuid,
        target_entity_uuid=entity.uuid
    )
    entity.add_condition(prone)

    # Should have immediately stood - movement consumed, NOT prone
    print(f"   Has Prone: {has_condition(entity, 'Prone')}")
    print(f"   Current movement: {entity.action_economy.movement.normalized_score}ft")

    assert not has_condition(entity, "Prone"), "Should NOT be prone (immediately stood up)"
    assert entity.action_economy.movement.normalized_score == initial_movement - 15, \
        f"Should have consumed 15ft movement, got {initial_movement - entity.action_economy.movement.normalized_score}ft"

    print("\n" + "=" * 60)
    print("PASS: Prone during own turn with movement - immediately stands!")
    print("=" * 60)


def test_prone_during_own_turn_no_movement():
    """Test that Prone stays when applied during own turn but no movement available."""
    print("\n" + "=" * 60)
    print("TEST: Prone During Own Turn (No Movement)")
    print("=" * 60)

    reset_combat_state()
    setup_arena()

    # Create entity
    entity = create_skeleton(name="Entity", position=(0, 0))
    entity.update_entity_senses()

    # Simulate turn start
    entity.on_turn_start()

    # Consume all movement
    entity.action_economy.consume("movement", 30)

    print(f"\n1. During own turn with no movement:")
    print(f"   Is my turn: {entity.is_my_turn}")
    print(f"   Current movement: {entity.action_economy.movement.normalized_score}ft")

    # Apply Prone during own turn
    print(f"\n2. Applying Prone during own turn...")
    from dnd.conditions import Prone
    prone = Prone(
        source_entity_uuid=entity.uuid,
        target_entity_uuid=entity.uuid
    )
    entity.add_condition(prone)

    # Should stay prone (not enough movement)
    print(f"   Has Prone: {has_condition(entity, 'Prone')}")

    assert has_condition(entity, "Prone"), "Should be prone (no movement to stand)"

    print("\n" + "=" * 60)
    print("PASS: Prone stays when no movement available!")
    print("=" * 60)


if __name__ == "__main__":
    test_prone_auto_stand()
    test_prone_not_auto_stand_on_other_turn()
    test_stand_up_no_longer_registered()
    test_prone_during_own_turn_with_movement()
    test_prone_during_own_turn_no_movement()
    print("\n" + "=" * 60)
    print("ALL TESTS PASSED!")
    print("=" * 60)
