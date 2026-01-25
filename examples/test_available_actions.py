"""
Test Available Actions System (Action Registry)

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
from dnd.actions import Dash, Dodge, Disengage, StandUp, Move
from dnd.actions_functional import get_available_actions, execute_by_index
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

    goblin, _ = setup_grid_and_entities(distance_tiles=1)

    actions_result = get_available_actions(goblin)

    # Should have entity_actions available (attacks with weapons)
    result.check(
        len(actions_result.entity_actions) > 0,
        f"Has attack options ({len(actions_result.entity_actions)} found)"
    )

    # Should have valid targets (skeleton is adjacent)
    if actions_result.entity_actions:
        attack_info = actions_result.entity_actions[0]
        result.check(
            len(attack_info.valid_targets) > 0,
            f"Has valid attack targets ({len(attack_info.valid_targets)} found)"
        )

    # Should have position_actions (movement) available
    result.check(
        len(actions_result.position_actions) > 0,
        f"Has movement option"
    )
    if actions_result.position_actions:
        move_info = actions_result.position_actions[0]
        result.check(
            len(move_info.valid_targets) > 0,
            f"Has valid movement positions ({len(move_info.valid_targets)} found)"
        )

    # Should have self_actions (Dash, Dodge, Disengage)
    # Note: StandUp only appears when Prone, DropProne is not a registered action
    self_action_names = [a.template_name for a in actions_result.self_actions]
    result.check("Dash" in self_action_names, "Has Dash action")
    result.check("Dodge" in self_action_names, "Has Dodge action")
    result.check("Disengage" in self_action_names, "Has Disengage action")

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

    # Check duration
    disengaging = goblin.active_conditions.get("Disengaging")
    if disengaging:
        result.check(
            disengaging.duration.duration == 1,
            f"Duration set to 1 round (got {disengaging.duration.duration})"
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
    """Test Prone condition and Stand Up action.

    Note: DropProne is not a registered action - Prone is applied by effects/spells.
    We test StandUp which is a registered action that requires Prone condition.
    """
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

    # Check available actions - Stand Up should NOT be available (not prone)
    actions_result = get_available_actions(goblin)
    self_action_names = [a.template_name for a in actions_result.self_actions]
    result.check("Stand Up" not in self_action_names, "Stand Up is NOT available (not prone)")

    # Apply Prone condition directly (simulating spell/effect knockdown)
    from dnd.conditions import Prone
    prone = Prone(source_entity_uuid=goblin.uuid, target_entity_uuid=goblin.uuid)
    goblin.add_condition(prone)
    result.check("Prone" in goblin.active_conditions, "Now Prone (from effect)")

    # Check available actions now show Stand Up
    actions_result = get_available_actions(goblin)
    self_action_names = [a.template_name for a in actions_result.self_actions]
    result.check("Stand Up" in self_action_names, "Stand Up IS available")

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
    """Test that blocking conditions prevent actions via action economy."""
    print("\n=== Test: Blocking Conditions ===")
    result = TestResult()

    goblin, _ = setup_grid_and_entities()

    # Normal state - can act
    actions_result = get_available_actions(goblin)
    result.check(len(actions_result.position_actions) > 0, "Normal: can move")
    result.check(len(actions_result.self_actions) > 0, "Normal: has actions")

    # Apply Incapacitated - sets action economy to 0
    incap = Incapacitated(source_entity_uuid=goblin.uuid, target_entity_uuid=goblin.uuid)
    goblin.add_condition(incap)

    actions_result = get_available_actions(goblin)
    # Incapacitated sets actions, bonus_actions, reactions, movement to 0
    # So all actions should fail pre_validate() due to can't afford costs
    result.check(
        len(actions_result.self_actions) == 0,
        f"Incapacitated: no self actions (got {len(actions_result.self_actions)})"
    )
    result.check(
        len(actions_result.position_actions) == 0,
        f"Incapacitated: no movement (got {len(actions_result.position_actions)})"
    )

    # Remove Incapacitated, apply Grappled (blocks movement only via max=0)
    goblin.remove_condition("Incapacitated")
    grappled = Grappled(source_entity_uuid=goblin.uuid, target_entity_uuid=goblin.uuid)
    goblin.add_condition(grappled)

    actions_result = get_available_actions(goblin)
    result.check(
        len(actions_result.position_actions) == 0,
        f"Grappled: cannot move (got {len(actions_result.position_actions)})"
    )
    result.check(
        len(actions_result.self_actions) > 0,
        "Grappled: CAN still take actions"
    )

    return result.summary()


def test_action_templates():
    """Test that action templates work correctly."""
    print("\n=== Test: Action Templates ===")
    result = TestResult()

    goblin, skeleton = setup_grid_and_entities(distance_tiles=1)

    # Check templates are registered
    result.check(len(goblin.registered_actions) > 0, f"Has registered actions ({len(goblin.registered_actions)})")

    # Check we have attack templates
    attack_templates = [a for a in goblin.registered_actions if a.target_type.value == "entity"]
    result.check(len(attack_templates) > 0, f"Has attack templates ({len(attack_templates)})")

    # Check we have move template
    move_template = goblin.get_action_template("Move")
    result.check(move_template is not None, "Has Move template")

    # Test template instantiation
    if attack_templates:
        template = attack_templates[0]
        result.check(template.template, "Template has template=True")

        # Set target and instantiate
        template.set_target_entity(skeleton.uuid)
        instance = template.instantiate(target_entity_uuid=skeleton.uuid)
        result.check(not instance.template, "Instance has template=False")
        result.check(instance.target_entity_uuid == skeleton.uuid, "Instance has correct target")

    return result.summary()


def test_execute_by_index():
    """Test executing actions by index."""
    print("\n=== Test: Execute by Index ===")
    result = TestResult()

    goblin, _ = setup_grid_and_entities(distance_tiles=1)

    # Get available actions
    available = get_available_actions(goblin)

    # Should have entity actions (attacks)
    if available.entity_actions:
        attack_info = available.entity_actions[0]
        target_count = len(attack_info.valid_targets)
        result.check(target_count > 0, f"Has attack targets ({target_count})")

        # Execute attack on first target
        event = execute_by_index(goblin, attack_info.template_name, 0)
        result.check(event is not None, "Attack executed")
        # HP might change depending on hit/miss

    return result.summary()


def run_all_tests():
    """Run all tests."""
    print("=" * 60)
    print("AVAILABLE ACTIONS SYSTEM TESTS (Action Registry)")
    print("=" * 60)

    tests = [
        ("Basic Available Actions", test_available_actions_basic),
        ("Dash Action", test_dash_action),
        ("Dodge Action", test_dodge_action),
        ("Disengage Action", test_disengage_action),
        ("Disengage Prevents OA", test_disengage_prevents_opportunity_attack),
        ("OA Without Disengage", test_opportunity_attack_without_disengage),
        ("Prone Actions", test_prone_actions),
        ("Condition Duration", test_condition_duration_at_turn_start),
        ("Blocking Conditions", test_blocking_conditions),
        ("Action Templates", test_action_templates),
        ("Execute by Index", test_execute_by_index),
    ]

    results = []
    for name, test_fn in tests:
        try:
            passed = test_fn()
            results.append((name, passed))
        except Exception as e:
            print(f"\n  ERROR in {name}: {e}")
            import traceback
            traceback.print_exc()
            results.append((name, False))

    # Summary
    print("\n" + "=" * 60)
    print("FINAL RESULTS")
    print("=" * 60)
    passed = sum(1 for _, p in results if p)
    failed = len(results) - passed
    print(f"\nPassed: {passed}/{len(results)}")
    if failed:
        print("Failed tests:")
        for name, p in results:
            if not p:
                print(f"  - {name}")

    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    exit(0 if success else 1)
