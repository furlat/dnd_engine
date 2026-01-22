"""
Test Available Actions System

Tests:
1. Available actions query returns correct options
2. Dash action applies Dashing condition with duration
3. Dodge action applies Dodging condition with duration
4. Disengage action prevents opportunity attacks
5. StandUp/DropProne actions work correctly
6. Condition duration advances at start of turn (not end)
"""

from typing import List

from dnd.core.gridmap import reset_map, get_map
from dnd.entity import Entity
from dnd.monsters.bestiary import create_goblin, create_skeleton
from dnd.available_actions import get_available_actions
from dnd.actions import Dash, Dodge, Disengage, StandUp, DropProne, Move
from dnd.conditions import Incapacitated, Grappled
from dnd.encounter import Encounter
from dnd.controller import PassController
from dnd.reactions import add_opportunity_attack_handler
from dnd.core.events import EventType, EventQueue


class TestResult:
    """Tracks test results."""
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.failures: List[str] = []

    def check(self, condition: bool, message: str) -> bool:
        if condition:
            self.passed += 1
            print(f"    ✓ {message}")
            return True
        else:
            self.failed += 1
            self.failures.append(message)
            print(f"    ✗ FAILED: {message}")
            return False

    def summary(self) -> bool:
        total = self.passed + self.failed
        print(f"\n  Results: {self.passed}/{total} passed")
        if self.failures:
            print("  Failures:")
            for f in self.failures:
                print(f"    - {f}")
        return self.failed == 0


def setup_clean_state():
    """Reset all registries for clean test state."""
    reset_map()
    Entity._entity_registry.clear()
    Entity._entity_by_position.clear()


def setup_grid_and_entities(distance_tiles: int = 1):
    """Set up grid and two entities at specified tile distance."""
    setup_clean_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 20, 20)

    goblin = create_goblin(name="Goblin", position=(5, 5))
    skeleton = create_skeleton(name="Skeleton", position=(5 + distance_tiles, 5))

    Entity.update_all_entities_senses()
    return goblin, skeleton


def test_available_actions_basic():
    """Test basic available actions query."""
    print("\n=== Test: Basic Available Actions Query ===")
    result = TestResult()

    goblin, _skeleton = setup_grid_and_entities(distance_tiles=1)

    actions_result = get_available_actions(goblin)

    # Should have attacks available (weapon + unarmed)
    result.check(
        len(actions_result.attacks) > 0,
        f"Has attack options ({len(actions_result.attacks)} found)"
    )

    # Should have valid targets (skeleton is adjacent)
    weapon_attacks = [a for a in actions_result.attacks if a.weapon_slot is not None]
    if weapon_attacks:
        result.check(
            len(weapon_attacks[0].valid_targets) > 0,
            f"Has valid attack targets ({len(weapon_attacks[0].valid_targets)} found)"
        )

    # Should have movement available
    result.check(
        len(actions_result.movement) > 0,
        f"Has movement option"
    )
    if actions_result.movement:
        result.check(
            len(actions_result.movement[0].valid_positions) > 0,
            f"Has valid movement positions ({len(actions_result.movement[0].valid_positions)} found)"
        )

    # Should have other actions (Dash, Dodge, Disengage)
    result.check(
        len(actions_result.other_actions) == 3,
        f"Has 3 other actions (Dash, Dodge, Disengage) - got {len(actions_result.other_actions)}"
    )
    action_ids = [a.action_id for a in actions_result.other_actions]
    result.check("dash" in action_ids, "Has Dash action")
    result.check("dodge" in action_ids, "Has Dodge action")
    result.check("disengage" in action_ids, "Has Disengage action")

    # Should have Drop Prone as free action (not prone yet)
    result.check(
        len(actions_result.free_actions) == 1,
        f"Has 1 free action - got {len(actions_result.free_actions)}"
    )
    if actions_result.free_actions:
        result.check(
            actions_result.free_actions[0].action_id == "drop_prone",
            "Free action is Drop Prone"
        )

    # No blocking conditions
    result.check(
        len(actions_result.blocking_conditions) == 0,
        f"No blocking conditions - got {actions_result.blocking_conditions}"
    )

    return result.summary()


def test_dash_action():
    """Test Dash action applies condition with correct duration."""
    print("\n=== Test: Dash Action ===")
    result = TestResult()

    goblin, _ = setup_grid_and_entities()

    # Get base movement
    base_mod = goblin.action_economy.movement.get_base_modifier()
    initial_movement = base_mod.value if base_mod else 30
    print(f"  Initial base movement: {initial_movement}ft")

    # Take Dash action
    dash = Dash(source_entity_uuid=goblin.uuid)
    event = dash.apply()
    assert event is not None

    result.check(not event.canceled, f"Dash succeeded (status: {event.status_message})")

    # Should have Dashing condition
    result.check(
        "Dashing" in goblin.active_conditions,
        "Has Dashing condition"
    )

    # Movement should be doubled
    new_movement = goblin.action_economy.movement.normalized_score
    result.check(
        new_movement == initial_movement * 2,
        f"Movement doubled: {initial_movement} -> {new_movement}"
    )

    # Should have used 1 action
    result.check(
        goblin.action_economy.actions.normalized_score == 0,
        f"Used 1 action (remaining: {goblin.action_economy.actions.normalized_score})"
    )

    # Check duration is set
    dashing = goblin.active_conditions.get("Dashing")
    if dashing:
        result.check(
            dashing.duration.duration == 1,
            f"Duration set to 1 round (got {dashing.duration.duration})"
        )

    return result.summary()


def test_dodge_action():
    """Test Dodge action applies condition."""
    print("\n=== Test: Dodge Action ===")
    result = TestResult()

    goblin, _ = setup_grid_and_entities()

    # Take Dodge action
    dodge = Dodge(source_entity_uuid=goblin.uuid)
    event = dodge.apply()
    assert event is not None

    result.check(not event.canceled, f"Dodge succeeded (status: {event.status_message})")

    # Should have Dodging condition
    result.check(
        "Dodging" in goblin.active_conditions,
        "Has Dodging condition"
    )

    # Should have used 1 action
    result.check(
        goblin.action_economy.actions.normalized_score == 0,
        f"Used 1 action (remaining: {goblin.action_economy.actions.normalized_score})"
    )

    # Check duration
    dodging = goblin.active_conditions.get("Dodging")
    if dodging:
        result.check(
            dodging.duration.duration == 1,
            f"Duration set to 1 round (got {dodging.duration.duration})"
        )

    return result.summary()


def test_disengage_action():
    """Test Disengage action applies condition."""
    print("\n=== Test: Disengage Action ===")
    result = TestResult()

    goblin, _ = setup_grid_and_entities()

    # Take Disengage action
    disengage = Disengage(source_entity_uuid=goblin.uuid)
    event = disengage.apply()
    assert event is not None

    result.check(not event.canceled, f"Disengage succeeded (status: {event.status_message})")

    # Should have Disengaging condition
    result.check(
        "Disengaging" in goblin.active_conditions,
        "Has Disengaging condition"
    )

    # Should have used 1 action
    result.check(
        goblin.action_economy.actions.normalized_score == 0,
        f"Used 1 action (remaining: {goblin.action_economy.actions.normalized_score})"
    )

    return result.summary()


def test_disengage_prevents_opportunity_attack():
    """Test that Disengage prevents opportunity attacks."""
    print("\n=== Test: Disengage Prevents Opportunity Attacks ===")
    result = TestResult()

    # Setup: goblin adjacent to skeleton
    goblin, skeleton = setup_grid_and_entities(distance_tiles=1)

    # Add opportunity attack handler to skeleton
    add_opportunity_attack_handler(skeleton)

    goblin_initial_hp = goblin.get_hp()
    print(f"  Goblin HP before: {goblin_initial_hp}")

    # Goblin takes Disengage action
    disengage = Disengage(source_entity_uuid=goblin.uuid)
    disengage.apply()
    result.check("Disengaging" in goblin.active_conditions, "Goblin has Disengaging condition")

    # Clear attack events before move
    # Goblin moves away from skeleton
    move = Move(source_entity_uuid=goblin.uuid, end_position=(5, 2))
    move_event = move.apply()
    assert move_event is not None

    result.check(not move_event.canceled, f"Move succeeded (status: {move_event.status_message})")
    result.check(goblin.position == (5, 2), f"Goblin moved to (5, 2) - got {goblin.position}")

    # Goblin should NOT have taken damage (no opportunity attack)
    goblin_final_hp = goblin.get_hp()
    result.check(
        goblin_final_hp == goblin_initial_hp,
        f"Goblin took no damage: HP still {goblin_final_hp}"
    )

    return result.summary()


def test_opportunity_attack_without_disengage():
    """Test that opportunity attacks DO happen without Disengage."""
    print("\n=== Test: Opportunity Attack Without Disengage ===")
    result = TestResult()

    # Setup: goblin adjacent to skeleton
    goblin, skeleton = setup_grid_and_entities(distance_tiles=1)

    # Add opportunity attack handler to skeleton
    add_opportunity_attack_handler(skeleton)

    print(f"  Goblin HP before: {goblin.get_hp()}")

    # Goblin moves away WITHOUT Disengaging
    result.check("Disengaging" not in goblin.active_conditions, "Goblin does NOT have Disengaging")

    move = Move(source_entity_uuid=goblin.uuid, end_position=(5, 2))
    move_event = move.apply()
    assert move_event is not None

    result.check(not move_event.canceled, "Move succeeded")

    # Check that an opportunity attack event was registered
    attack_events = EventQueue.get_events_by_type(EventType.ATTACK)
    oa_events = [e for e in attack_events if "Opportunity" in e.name]
    result.check(
        len(oa_events) > 0,
        f"Opportunity attack was triggered ({len(oa_events)} OA events found)"
    )

    return result.summary()


def test_prone_actions():
    """Test Drop Prone and Stand Up actions."""
    print("\n=== Test: Prone Actions ===")
    result = TestResult()

    goblin, _ = setup_grid_and_entities()

    # Get base movement for later
    base_mod = goblin.action_economy.movement.get_base_modifier()
    base_movement = base_mod.value if base_mod else 30
    half_movement = base_movement // 2
    print(f"  Base movement: {base_movement}ft, half: {half_movement}ft")

    # Should not be prone initially
    result.check("Prone" not in goblin.active_conditions, "Not prone initially")

    # Check available actions show Drop Prone, not Stand Up
    actions_result = get_available_actions(goblin)
    result.check(
        any(a.action_id == "drop_prone" for a in actions_result.free_actions),
        "Drop Prone is available"
    )
    result.check(
        not any(a.action_id == "stand_up" for a in actions_result.movement),
        "Stand Up is NOT available"
    )

    # Drop prone
    drop = DropProne(source_entity_uuid=goblin.uuid)
    event = drop.apply()
    assert event is not None
    result.check(not event.canceled, "Drop Prone succeeded")
    result.check("Prone" in goblin.active_conditions, "Now Prone")

    # Check available actions now show Stand Up, not Drop Prone
    actions_result = get_available_actions(goblin)
    result.check(
        not any(a.action_id == "drop_prone" for a in actions_result.free_actions),
        "Drop Prone is NOT available while prone"
    )
    stand_up_actions = [a for a in actions_result.movement if a.action_id == "stand_up"]
    result.check(len(stand_up_actions) == 1, "Stand Up IS available")

    # Stand up (costs half movement)
    initial_movement = goblin.action_economy.movement.normalized_score
    stand = StandUp(source_entity_uuid=goblin.uuid)
    event = stand.apply()
    assert event is not None
    result.check(not event.canceled, "Stand Up succeeded")
    result.check("Prone" not in goblin.active_conditions, "No longer Prone")

    # Check movement was consumed
    remaining = goblin.action_economy.movement.normalized_score
    expected = initial_movement - half_movement
    result.check(
        remaining == expected,
        f"Movement consumed: {initial_movement} - {half_movement} = {remaining} (expected {expected})"
    )

    return result.summary()


def test_condition_duration_at_turn_start():
    """Test that conditions expire at start of turn, not end."""
    print("\n=== Test: Condition Duration Advances at Turn Start ===")
    result = TestResult()

    goblin, skeleton = setup_grid_and_entities(distance_tiles=5)

    # Create encounter with controllers
    from uuid import uuid4
    encounter = Encounter(name="Test Encounter", source_entity_uuid=uuid4())

    # Add combatants with PassControllers
    goblin_controller = PassController(source_entity_uuid=goblin.uuid)
    skeleton_controller = PassController(source_entity_uuid=skeleton.uuid)

    encounter.add_combatant(goblin, goblin_controller)
    encounter.add_combatant(skeleton, skeleton_controller)

    encounter.roll_initiative()
    encounter.start_encounter()

    # Get first combatant
    first_uuid = encounter.initiative_order[0]
    first = Entity.get(first_uuid)
    if not first:
        print("    ✗ FAILED: Could not get first combatant")
        return False
    print(f"  First combatant: {first.name}")

    # Start first turn
    encounter.start_turn()

    # Take Dodge action
    dodge = Dodge(source_entity_uuid=first.uuid)
    dodge.apply()
    result.check("Dodging" in first.active_conditions, f"{first.name} used Dodge")

    # End turn (don't use end_turn - next_turn handles it)
    result.check(
        "Dodging" in first.active_conditions,
        "Dodging persists during turn"
    )

    # next_turn does: end current turn + advance index + start new turn
    encounter.next_turn()  # Ends Goblin turn, starts Skeleton turn

    result.check(
        "Dodging" in first.active_conditions,
        "Dodging persists through other's turn"
    )

    # Back to first combatant's turn
    encounter.next_turn()  # Ends Skeleton turn, starts Goblin turn (should expire Dodging)

    result.check(
        "Dodging" not in first.active_conditions,
        f"Dodging expired at start of {first.name}'s next turn"
    )

    return result.summary()


def test_blocking_conditions():
    """Test that blocking conditions prevent actions."""
    print("\n=== Test: Blocking Conditions ===")
    result = TestResult()

    goblin, _ = setup_grid_and_entities()

    # Normal state - can act
    actions_result = get_available_actions(goblin)
    result.check(actions_result.can_move, "Normal: can move")
    result.check(len(actions_result.other_actions) > 0, "Normal: has actions")

    # Apply Incapacitated
    incap = Incapacitated(source_entity_uuid=goblin.uuid, target_entity_uuid=goblin.uuid)
    goblin.add_condition(incap)

    actions_result = get_available_actions(goblin)
    result.check(not actions_result.can_move, "Incapacitated: cannot move")
    result.check(
        len(actions_result.other_actions) == 0,
        f"Incapacitated: no actions (got {len(actions_result.other_actions)})"
    )
    result.check(
        "Incapacitated" in actions_result.blocking_conditions,
        f"Reports Incapacitated blocking (got {actions_result.blocking_conditions})"
    )

    # Remove Incapacitated, apply Grappled (blocks movement only)
    goblin.remove_condition("Incapacitated")
    grappled = Grappled(source_entity_uuid=goblin.uuid, target_entity_uuid=goblin.uuid)
    goblin.add_condition(grappled)

    actions_result = get_available_actions(goblin)
    result.check(not actions_result.can_move, "Grappled: cannot move")
    result.check(
        len(actions_result.other_actions) > 0,
        "Grappled: CAN still take actions"
    )
    result.check(
        "Grappled" in actions_result.blocking_conditions,
        f"Reports Grappled blocking (got {actions_result.blocking_conditions})"
    )

    return result.summary()


def run_all_tests():
    """Run all tests."""
    print("=" * 60)
    print("AVAILABLE ACTIONS SYSTEM TESTS")
    print("=" * 60)

    all_tests = [
        ("Basic Available Actions", test_available_actions_basic),
        ("Dash Action", test_dash_action),
        ("Dodge Action", test_dodge_action),
        ("Disengage Action", test_disengage_action),
        ("Disengage Prevents OA", test_disengage_prevents_opportunity_attack),
        ("OA Without Disengage", test_opportunity_attack_without_disengage),
        ("Prone Actions", test_prone_actions),
        ("Condition Duration at Turn Start", test_condition_duration_at_turn_start),
        ("Blocking Conditions", test_blocking_conditions),
    ]

    passed = 0
    failed = 0
    failed_tests = []

    for name, test_fn in all_tests:
        try:
            if test_fn():
                passed += 1
            else:
                failed += 1
                failed_tests.append(name)
        except Exception as e:
            failed += 1
            failed_tests.append(f"{name} (EXCEPTION: {e})")
            import traceback
            traceback.print_exc()

    print("\n" + "=" * 60)
    print("FINAL RESULTS")
    print("=" * 60)
    print(f"\n  Tests passed: {passed}/{passed + failed}")

    if failed_tests:
        print(f"\n  FAILED TESTS:")
        for t in failed_tests:
            print(f"    - {t}")
        print("\n  SOME TESTS FAILED!")
        return False
    else:
        print("\n  ALL TESTS PASSED!")
        return True


if __name__ == "__main__":
    success = run_all_tests()
    exit(0 if success else 1)
