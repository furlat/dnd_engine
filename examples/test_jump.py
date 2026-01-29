"""
Test Jump Action - LOS-Based Position Targeting

Tests the Jump action which:
1. Uses POSITION_LOS targeting (visible positions, not path-reachable)
2. Has dynamic range based on STR (15ft base + 5ft per STR mod point)
3. Costs bonus action + movement equal to distance
4. Can bypass obstacles but must land on walkable, unoccupied tile
"""

from uuid import uuid4

from dnd.utils import reset_combat_state
from dnd.core.gridmap import get_map
from dnd.entity import Entity, EntityConfig
from dnd.blocks.abilities import AbilityScoresConfig, AbilityConfig
from dnd.actions_functional import setup_standard_actions, get_available_actions
from dnd.actions import Jump
from dnd.core.base_actions import TargetType
from dnd.core.modifiers import NumericalModifier


def test_jump_range_calculation():
    """Test that jump range scales with STR."""
    print("\n=== Test Jump Range Calculation ===")
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 20, 20)

    # Create entity with STR 10 (mod +0)
    weak_config = EntityConfig(
        ability_scores=AbilityScoresConfig(
            strength=AbilityConfig(ability_score=10)
        ),
        position=(5, 5)
    )
    weak = Entity.create(name="Weak", source_entity_uuid=uuid4(), config=weak_config)
    setup_standard_actions(weak)
    Entity.update_all_entities_senses()

    # Create entity with STR 18 (mod +4)
    strong_config = EntityConfig(
        ability_scores=AbilityScoresConfig(
            strength=AbilityConfig(ability_score=18)
        ),
        position=(10, 10)
    )
    strong = Entity.create(name="Strong", source_entity_uuid=uuid4(), config=strong_config)
    setup_standard_actions(strong)
    Entity.update_all_entities_senses()

    # Get jump templates
    weak_jump = weak.get_action_template("Jump")
    strong_jump = strong.get_action_template("Jump")

    assert weak_jump is not None, "Weak should have Jump action"
    assert strong_jump is not None, "Strong should have Jump action"

    # Check ranges
    weak_range = weak_jump.get_range()
    strong_range = strong_jump.get_range()

    assert weak_range is not None, "Jump should return a range"
    assert strong_range is not None, "Jump should return a range"

    print(f"Weak (STR 10, mod +0): Jump range = {weak_range.normal}ft")
    print(f"Strong (STR 18, mod +4): Jump range = {strong_range.normal}ft")

    assert weak_range.normal == 15, f"Expected 15ft for STR 10, got {weak_range.normal}ft"
    assert strong_range.normal == 35, f"Expected 35ft for STR 18, got {strong_range.normal}ft"

    print("PASSED: Jump range scales with STR correctly")


def test_jump_valid_positions():
    """Test that Jump returns valid positions based on LOS and range.

    This test creates a scenario where Jump can reach a position that Move cannot.
    We create an isolated island platform separated by water (visible but not walkable).

    Key insight: Empty space (no tile) blocks LOS! We use water tiles
    (visible=True, walkable=False) to allow LOS but prevent path movement.
    """
    print("\n=== Test Jump Valid Positions ===")
    reset_combat_state()
    grid = get_map()

    # Create main platform (0-4, 0-4)
    for x in range(5):
        for y in range(5):
            grid.set_tile(x, y, walkable=True, visible=True, name="Floor")

    # Create water gap (5-7, 0-4) - visible but not walkable
    # This allows LOS to pass through but prevents walking
    for x in range(5, 8):
        for y in range(5):
            grid.set_tile(x, y, walkable=False, visible=True, name="Water")

    # Create isolated island platform (8-10, 2-4)
    # Visible through water, but not path-connected
    for x in range(8, 11):
        for y in range(2, 5):
            grid.set_tile(x, y, walkable=True, visible=True, name="Island")

    # Entity on main platform
    config = EntityConfig(
        ability_scores=AbilityScoresConfig(
            strength=AbilityConfig(ability_score=18)  # +4 mod = 35ft range
        ),
        position=(2, 2)
    )
    jumper = Entity.create(name="Jumper", source_entity_uuid=uuid4(), config=config)
    setup_standard_actions(jumper)
    Entity.update_all_entities_senses()

    jump_template = jumper.get_action_template("Jump")
    assert jump_template is not None

    valid_jump_positions = jump_template.get_valid_positions()

    print(f"Entity position: {jumper.position}")
    print(f"Jump range: {jump_template.get_range().normal}ft")  # type: ignore
    print(f"Valid jump positions count: {len(valid_jump_positions)}")

    # Target on the island - should be visible and in range
    target_pos = (9, 3)
    distance_to_target = jumper.senses.get_feet_distance(target_pos)
    print(f"Distance to {target_pos}: {distance_to_target}ft")
    print(f"Is {target_pos} visible: {target_pos in jumper.senses.visible and jumper.senses.visible[target_pos]}")
    print(f"Is {target_pos} in valid jump positions: {target_pos in valid_jump_positions}")

    # This might fail if LOS algorithm doesn't see through empty space
    # Let's check what IS valid for jump
    if valid_jump_positions:
        print(f"Sample jump positions (first 5): {list(valid_jump_positions)[:5]}")

    # Check Move positions
    available = get_available_actions(jumper)
    move_positions = set()
    for action_info in available.position_actions:
        if action_info.template_name == "Move":
            for target in action_info.valid_targets:
                if target.position:
                    move_positions.add(target.position)

    print(f"Valid move positions count: {len(move_positions)}")

    # The key test: Jump should include more positions than Move
    # because Jump uses LOS while Move uses paths
    jump_only = set(valid_jump_positions) - move_positions
    print(f"Positions reachable by Jump but not Move: {len(jump_only)}")

    # We expect Jump to reach the island positions that Move cannot
    island_positions_in_jump = [p for p in valid_jump_positions if p[0] >= 8]
    island_positions_in_move = [p for p in move_positions if p[0] >= 8]

    print(f"Island positions reachable by Jump: {len(island_positions_in_jump)}")
    print(f"Island positions reachable by Move: {len(island_positions_in_move)}")

    # Main assertion: Jump can reach island, Move cannot
    assert len(island_positions_in_jump) > 0 or len(jump_only) > 0, \
        "Jump should reach some positions that Move cannot"
    assert len(island_positions_in_move) == 0, \
        "Move should NOT reach island positions (no path)"

    print("PASSED: Jump can reach positions that Move cannot")


def test_jump_execution():
    """Test that Jump actually moves the entity."""
    print("\n=== Test Jump Execution ===")
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 20, 20)

    config = EntityConfig(
        ability_scores=AbilityScoresConfig(
            strength=AbilityConfig(ability_score=16)  # +3 mod = 30ft range
        ),
        position=(5, 5)
    )
    jumper = Entity.create(name="Jumper", source_entity_uuid=uuid4(), config=config)
    setup_standard_actions(jumper)
    Entity.update_all_entities_senses()

    initial_pos = jumper.position
    target_pos = (8, 5)  # 15ft away (3 squares * 5ft)

    # Check initial state
    initial_bonus_actions = jumper.action_economy.bonus_actions.normalized_score
    initial_movement = jumper.action_economy.movement.normalized_score

    print(f"Initial position: {initial_pos}")
    print(f"Target position: {target_pos}")
    print(f"Initial bonus actions: {initial_bonus_actions}")
    print(f"Initial movement: {initial_movement}ft")

    # Execute jump
    jump = Jump(
        source_entity_uuid=jumper.uuid,
        end_position=target_pos,
        template=False
    )
    event = jump.apply()

    assert event is not None, "Jump should return an event"
    assert not event.canceled, f"Jump should not be canceled: {event.status_message}"

    final_pos = jumper.position
    final_bonus_actions = jumper.action_economy.bonus_actions.normalized_score
    final_movement = jumper.action_economy.movement.normalized_score

    print(f"Final position: {final_pos}")
    print(f"Final bonus actions: {final_bonus_actions}")
    print(f"Final movement: {final_movement}ft")

    assert final_pos == target_pos, f"Expected position {target_pos}, got {final_pos}"
    assert final_bonus_actions == initial_bonus_actions - 1, "Jump should cost 1 bonus action"

    # Movement cost should be equal to distance jumped (15ft)
    expected_movement = initial_movement - 15
    assert final_movement == expected_movement, f"Expected {expected_movement}ft movement, got {final_movement}ft"

    print("PASSED: Jump moves entity and consumes correct resources")


def test_jump_occupied_position():
    """Test that Jump cannot land on occupied positions."""
    print("\n=== Test Jump Cannot Land on Occupied Position ===")
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 20, 20)

    # Create jumper
    config1 = EntityConfig(
        ability_scores=AbilityScoresConfig(strength=AbilityConfig(ability_score=16)),
        position=(5, 5)
    )
    jumper = Entity.create(name="Jumper", source_entity_uuid=uuid4(), config=config1)
    setup_standard_actions(jumper)

    # Create blocker at target position
    config2 = EntityConfig(position=(8, 5))
    blocker = Entity.create(name="Blocker", source_entity_uuid=uuid4(), config=config2)
    setup_standard_actions(blocker)

    Entity.update_all_entities_senses()

    # Try to jump to occupied position
    jump = Jump(
        source_entity_uuid=jumper.uuid,
        end_position=(8, 5),  # Blocker is here
        template=False
    )
    event = jump.apply()

    print(f"Jump to occupied position result: {event.canceled if event else 'None'}")
    if event:
        print(f"Status: {event.status_message}")

    assert event is None or event.canceled, "Jump to occupied position should fail"
    assert jumper.position == (5, 5), "Jumper should not have moved"

    print("PASSED: Jump cannot land on occupied position")


def test_jump_movement_budget():
    """Test that Jump respects movement budget."""
    print("\n=== Test Jump Respects Movement Budget ===")
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 30, 30)

    config = EntityConfig(
        ability_scores=AbilityScoresConfig(
            strength=AbilityConfig(ability_score=20)  # +5 mod = 40ft range
        ),
        position=(5, 5)
    )
    jumper = Entity.create(name="Jumper", source_entity_uuid=uuid4(), config=config)
    setup_standard_actions(jumper)
    Entity.update_all_entities_senses()

    # Consume most movement using proper modifier pattern
    movement_spent_modifier = NumericalModifier.create(
        source_entity_uuid=jumper.uuid,
        name="Movement Spent",
        value=-25  # Only 5ft left from base 30ft
    )
    jumper.action_economy.movement.self_static.add_value_modifier(movement_spent_modifier)

    remaining = jumper.action_economy.movement.normalized_score
    print(f"Remaining movement: {remaining}ft")
    jump_template = jumper.get_action_template('Jump')
    jump_range = jump_template.get_range() if jump_template else None
    print(f"Jump range: {jump_range.normal if jump_range else 'N/A'}ft")

    # Try to jump 20ft (more than remaining movement)
    target_20ft = (9, 5)  # 20ft away
    jump = Jump(
        source_entity_uuid=jumper.uuid,
        end_position=target_20ft,
        template=False
    )
    event = jump.apply()

    print(f"Jump 20ft with 5ft remaining: {event.canceled if event else 'Failed'}")

    assert event is None or event.canceled, "Jump beyond movement budget should fail"

    # But 5ft jump should work (1 square)
    target_5ft = (6, 5)
    jump_short = Jump(
        source_entity_uuid=jumper.uuid,
        end_position=target_5ft,
        template=False
    )
    event_short = jump_short.apply()

    print(f"Jump 5ft with 5ft remaining: {'Success' if event_short and not event_short.canceled else 'Failed'}")

    assert event_short is not None and not event_short.canceled, "5ft jump should succeed"
    assert jumper.position == target_5ft, "Jumper should have moved"

    print("PASSED: Jump respects movement budget")


def test_jump_in_available_actions():
    """Test that Jump appears in available actions with POSITION_LOS type."""
    print("\n=== Test Jump in Available Actions ===")
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 20, 20)

    config = EntityConfig(
        ability_scores=AbilityScoresConfig(strength=AbilityConfig(ability_score=14)),
        position=(5, 5)
    )
    jumper = Entity.create(name="Jumper", source_entity_uuid=uuid4(), config=config)
    setup_standard_actions(jumper)
    Entity.update_all_entities_senses()

    available = get_available_actions(jumper)

    # Find Jump in position actions
    jump_action = None
    for action_info in available.position_actions:
        if action_info.template_name == "Jump":
            jump_action = action_info
            break

    assert jump_action is not None, "Jump should appear in available position actions"
    assert jump_action.target_type == TargetType.POSITION_LOS, f"Jump should have POSITION_LOS type, got {jump_action.target_type}"
    print(f"Jump action found with {len(jump_action.valid_targets)} valid targets")
    print(f"Target type: {jump_action.target_type}")
    print(f"Cost type: {jump_action.cost_type}")

    print("PASSED: Jump appears in available actions with correct target type")


if __name__ == "__main__":
    test_jump_range_calculation()
    test_jump_valid_positions()
    test_jump_execution()
    test_jump_occupied_position()
    test_jump_movement_budget()
    test_jump_in_available_actions()

    print("\n" + "=" * 50)
    print("All Jump action tests passed!")
    print("=" * 50)
