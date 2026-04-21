"""
Fighter Combat Simulation Test

Tests that a Fighter created with the factory has all expected actions available:
- Standard actions (Move, Dash, Dodge, Disengage)
- Attack actions based on equipped weapons
- Second Wind (bonus action, heals 1d10 + fighter level)
- Action Surge (grants extra action)
- Extra Attack (at L5+, can make additional attack after attacking)

Also simulates a combat sequence demonstrating these features.
"""

from typing import List

from dnd.core.gridmap import reset_map, get_map
from dnd.entity import Entity
from dnd.monsters.bestiary import create_skeleton
from dnd.classes.fighter_factory import FighterConfig, create_fighter
from dnd.actions_functional import get_available_actions, execute_action
from dnd.encounter import Encounter
from dnd.controller import PassController
from dnd.core.events import EventQueue


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
    EventQueue.reset()


def setup_fighter_vs_skeleton(fighter_level: int = 5, distance_tiles: int = 1):
    """Set up grid with a Fighter and Skeleton at specified distance."""
    setup_clean_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 20, 20)

    # Create Fighter at specified level
    config = FighterConfig(
        level=fighter_level,
        name="Test Fighter",
        position=(5, 5),
        base_strength=15,
        base_dexterity=13,
        base_constitution=14,
        base_intelligence=10,
        base_wisdom=12,
        base_charisma=8,
        bonus_plus_2="strength",
        bonus_plus_1="constitution",
        fighting_style="defense",
        equipment_preset="sword_shield",
        # ASIs for higher levels
        asi_4=[("strength", 2)] if fighter_level >= 4 else None,
        asi_6=[("constitution", 2)] if fighter_level >= 6 else None,
        asi_8=[("strength", 2)] if fighter_level >= 8 else None,
        asi_12=[("constitution", 2)] if fighter_level >= 12 else None,
        asi_14=[("strength", 2)] if fighter_level >= 14 else None,
        asi_16=[("constitution", 2)] if fighter_level >= 16 else None,
        asi_19=[("strength", 2)] if fighter_level >= 19 else None,
    )
    fighter = create_fighter(config)

    # Create Skeleton as opponent
    skeleton = create_skeleton(name="Skeleton", position=(5 + distance_tiles, 5))

    Entity.update_all_entities_senses()
    return fighter, skeleton


def test_fighter_available_actions_level_1():
    """Test Level 1 Fighter has correct actions available."""
    print("\n=== Test: Level 1 Fighter Available Actions ===")
    result = TestResult()

    fighter, _skeleton = setup_fighter_vs_skeleton(fighter_level=1, distance_tiles=1)

    print(f"  Fighter HP: {fighter.get_hp()}, AC: {fighter.ac_bonus().normalized_score}")
    print(f"  Fighter conditions: {list(fighter.active_conditions.keys())}")

    # Get available actions
    actions = get_available_actions(fighter)

    # Check all action names
    all_action_names = [a.template_name for a in actions.all_actions]
    print(f"  Available actions: {all_action_names}")

    # Standard actions
    result.check("Move" in all_action_names, "Has Move action")
    result.check("Dash" in all_action_names, "Has Dash action")
    result.check("Dodge" in all_action_names, "Has Dodge action")
    result.check("Disengage" in all_action_names, "Has Disengage action")

    # Attack action (equipped longsword)
    result.check("Attack_MELEE_MAIN" in all_action_names, "Has Attack_MELEE_MAIN action")

    # Second Wind (from SecondWindFeature) - only shows when damaged
    # Since fighter is at full health, Second Wind won't show
    # Instead, verify the condition/resource exists
    result.check("Second Wind Feature" in fighter.active_conditions, "Has Second Wind Feature condition")
    result.check(fighter.action_economy.has_resource("second_wind"), "Has second_wind resource")

    # Should NOT have Action Surge or Extra Attack at L1
    result.check("Action Surge" not in all_action_names, "No Action Surge at L1")
    extra_attack_actions = [a for a in all_action_names if a.startswith("Extra Attack")]
    result.check(len(extra_attack_actions) == 0, "No Extra Attack at L1")

    return result.summary()


def test_fighter_available_actions_level_5():
    """Test Level 5 Fighter has all class features as actions."""
    print("\n=== Test: Level 5 Fighter Available Actions ===")
    result = TestResult()

    fighter, _skeleton = setup_fighter_vs_skeleton(fighter_level=5, distance_tiles=1)

    print(f"  Fighter HP: {fighter.get_hp()}, AC: {fighter.ac_bonus().normalized_score}")
    print(f"  Fighter conditions: {list(fighter.active_conditions.keys())}")

    # Get available actions
    actions = get_available_actions(fighter)

    # Check all action names
    all_action_names = [a.template_name for a in actions.all_actions]
    print(f"  Available actions: {all_action_names}")

    # Standard actions
    result.check("Move" in all_action_names, "Has Move action")
    result.check("Dash" in all_action_names, "Has Dash action")
    result.check("Dodge" in all_action_names, "Has Dodge action")
    result.check("Disengage" in all_action_names, "Has Disengage action")

    # Attack action
    result.check("Attack_MELEE_MAIN" in all_action_names, "Has Attack_MELEE_MAIN action")

    # Fighter class features
    # Second Wind only shows when damaged - check resource exists
    result.check("Second Wind Feature" in fighter.active_conditions, "Has Second Wind Feature")
    result.check(fighter.action_economy.has_resource("second_wind"), "Has second_wind resource")
    result.check("Action Surge" in all_action_names, "Has Action Surge action (L2)")

    # Extra Attack (L5) - only shows AFTER first attack (HasAttacked condition)
    # Before attacking, it won't appear
    result.check(
        "Extra Attack" in fighter.active_conditions,
        "Has Extra Attack Feature condition"
    )

    return result.summary()


def test_second_wind_action():
    """Test Second Wind action heals the fighter."""
    print("\n=== Test: Second Wind Action ===")
    result = TestResult()

    fighter, _skeleton = setup_fighter_vs_skeleton(fighter_level=5, distance_tiles=1)

    # Deal some damage to fighter
    initial_hp = fighter.get_hp()
    fighter.health.add_damage(20)  # Take 20 damage
    damaged_hp = fighter.get_hp()
    print(f"  Fighter HP: {initial_hp} -> {damaged_hp} (after 20 damage)")

    result.check(damaged_hp < initial_hp, f"Fighter is damaged ({damaged_hp} < {initial_hp})")

    # Get Second Wind action info
    actions = get_available_actions(fighter)
    second_wind_info = None
    for action_info in actions.all_actions:
        if action_info.template_name == "Second Wind":
            second_wind_info = action_info
            break

    result.check(second_wind_info is not None, "Second Wind action is available")

    if second_wind_info:
        # Second Wind is a self-targeting action
        result.check(
            len(second_wind_info.valid_targets) > 0,
            "Second Wind has valid targets (self)"
        )

        # Execute Second Wind
        event = execute_action(fighter, "Second Wind", second_wind_info.valid_targets[0])
        result.check(event is not None, "Second Wind executed")

        if event and not event.canceled:
            healed_hp = fighter.get_hp()
            healing_done = healed_hp - damaged_hp
            print(f"  HP after Second Wind: {healed_hp} (healed {healing_done})")
            result.check(healed_hp > damaged_hp, f"Fighter was healed ({healed_hp} > {damaged_hp})")
        else:
            print(f"  Second Wind was canceled or failed: {event.status_message if event else 'No event'}")

        # Check Second Wind resource was consumed
        sw_current = fighter.action_economy.get_resource_current("second_wind")
        result.check(sw_current == 0, f"Second Wind resource consumed (remaining: {sw_current})")

    return result.summary()


def test_action_surge_grants_extra_action():
    """Test Action Surge grants an additional action."""
    print("\n=== Test: Action Surge Grants Extra Action ===")
    result = TestResult()

    fighter, _skeleton = setup_fighter_vs_skeleton(fighter_level=5, distance_tiles=1)

    # Check initial action economy
    initial_actions = fighter.action_economy.actions.normalized_score
    print(f"  Initial actions: {initial_actions}")
    result.check(initial_actions == 1, "Fighter has 1 action initially")

    # Get Action Surge action info
    actions = get_available_actions(fighter)
    action_surge_info = None
    for action_info in actions.all_actions:
        if action_info.template_name == "Action Surge":
            action_surge_info = action_info
            break

    result.check(action_surge_info is not None, "Action Surge action is available")

    if action_surge_info:
        # Execute Action Surge
        event = execute_action(fighter, "Action Surge", action_surge_info.valid_targets[0])
        result.check(event is not None and not event.canceled, "Action Surge executed successfully")

        # Check we now have more actions
        current_actions = fighter.action_economy.actions.normalized_score
        print(f"  Actions after Action Surge: {current_actions}")
        result.check(current_actions == 2, f"Fighter now has 2 actions ({current_actions})")

        # Check Action Surge resource was consumed
        as_current = fighter.action_economy.get_resource_current("action_surge")
        result.check(as_current == 0, f"Action Surge resource consumed (remaining: {as_current})")

    return result.summary()


def test_extra_attack_workflow():
    """Test Extra Attack workflow - attack once, Extra Attack becomes available."""
    print("\n=== Test: Extra Attack Workflow ===")
    result = TestResult()

    fighter, skeleton = setup_fighter_vs_skeleton(fighter_level=5, distance_tiles=1)

    skeleton_initial_hp = skeleton.get_hp()
    print(f"  Skeleton HP: {skeleton_initial_hp}")

    # Get available actions before attacking
    actions_before = get_available_actions(fighter)
    all_names_before = [a.template_name for a in actions_before.all_actions]

    # Extra Attack should be available (or Attack is, and Extra Attack appears after)
    has_attack = "Attack_MELEE_MAIN" in all_names_before
    result.check(has_attack, "Has Attack_MELEE_MAIN before attacking")

    # Check for Extra Attack action before first attack
    has_extra_before = "Extra Attack_MELEE_MAIN" in all_names_before
    print(f"  Has Extra Attack before attacking: {has_extra_before}")
    print(f"  Actions before: {all_names_before}")

    # Execute first attack
    attack_info = None
    for info in actions_before.entity_actions:
        if info.template_name == "Attack_MELEE_MAIN":
            attack_info = info
            break

    if attack_info and len(attack_info.valid_targets) > 0:
        event = execute_action(fighter, "Attack_MELEE_MAIN", attack_info.valid_targets[0])
        result.check(event is not None, "First attack executed")
        print(f"  First attack result: {event.status_message if event else 'None'}")

    # Check for HasAttacked condition (named "Has Attacked" or might be internal)
    # Note: The condition might be applied but the Extra Attack action becoming available is the key test
    has_attacked_applied = "Has Attacked" in fighter.active_conditions or "HasAttacked" in fighter.active_conditions
    result.check(has_attacked_applied, f"HasAttacked condition applied (conditions: {list(fighter.active_conditions.keys())})")

    # Get available actions after first attack - Extra Attack should now be usable
    actions_after = get_available_actions(fighter)
    all_names_after = [a.template_name for a in actions_after.all_actions]
    print(f"  Actions after first attack: {all_names_after}")

    # The Extra Attack action should be available (depends on implementation)
    # Check if we still have attack options
    extra_attack_info = None
    for info in actions_after.entity_actions:
        if info.template_name == "Extra Attack_MELEE_MAIN":
            extra_attack_info = info
            break

    if extra_attack_info and len(extra_attack_info.valid_targets) > 0:
        result.check(True, "Extra Attack_MELEE_MAIN is available after first attack")

        # Execute Extra Attack
        event2 = execute_action(fighter, "Extra Attack_MELEE_MAIN", extra_attack_info.valid_targets[0])
        result.check(event2 is not None, "Extra Attack executed")
        print(f"  Extra Attack result: {event2.status_message if event2 else 'None'}")
    else:
        # Extra Attack might have different mechanics - check what's available
        entity_action_names = [a.template_name for a in actions_after.entity_actions]
        result.check(
            False,
            f"Extra Attack not found in entity_actions. Available: {entity_action_names}"
        )

    return result.summary()


def test_full_combat_round():
    """Simulate a full combat round with Fighter using all abilities."""
    print("\n=== Test: Full Combat Round Simulation ===")
    result = TestResult()

    fighter, skeleton = setup_fighter_vs_skeleton(fighter_level=5, distance_tiles=1)

    print(f"  Fighter: HP={fighter.get_hp()}, AC={fighter.ac_bonus().normalized_score}")
    print(f"  Skeleton: HP={skeleton.get_hp()}, AC={skeleton.ac_bonus().normalized_score}")
    print(f"  Fighter conditions: {list(fighter.active_conditions.keys())}")

    # Create encounter
    from uuid import uuid4
    encounter = Encounter(name="Test Combat", source_entity_uuid=uuid4())

    # Add combatants
    fighter_controller = PassController(source_entity_uuid=fighter.uuid)
    skeleton_controller = PassController(source_entity_uuid=skeleton.uuid)

    encounter.add_combatant(fighter, fighter_controller)
    encounter.add_combatant(skeleton, skeleton_controller)

    encounter.roll_initiative()
    encounter.start_encounter()

    print("\n  --- Combat Log ---")

    # Manually control fighter's turn
    # Force fighter to go first for testing
    encounter.current_turn_index = encounter.initiative_order.index(fighter.uuid)
    encounter.start_turn()

    # 1. Use Action Surge to get extra action
    actions = get_available_actions(fighter)
    action_surge_info = next((a for a in actions.all_actions if a.template_name == "Action Surge"), None)
    if action_surge_info:
        execute_action(fighter, "Action Surge", action_surge_info.valid_targets[0])
        print(f"  > Fighter uses Action Surge! Actions now: {fighter.action_economy.actions.normalized_score}")
        result.check(
            fighter.action_economy.actions.normalized_score == 2,
            "Action Surge granted extra action"
        )

    # 2. First Attack
    actions = get_available_actions(fighter)
    attack_info = next((a for a in actions.entity_actions if a.template_name == "Attack_MELEE_MAIN"), None)
    if attack_info and attack_info.valid_targets:
        event = execute_action(fighter, "Attack_MELEE_MAIN", attack_info.valid_targets[0])
        print(f"  > Fighter attacks Skeleton: {event.status_message if event else 'Failed'}")
        result.check(event is not None, "First attack executed")

    # 3. Extra Attack (if available)
    actions = get_available_actions(fighter)
    extra_info = next((a for a in actions.entity_actions if a.template_name == "Extra Attack_MELEE_MAIN"), None)
    if extra_info and extra_info.valid_targets:
        event = execute_action(fighter, "Extra Attack_MELEE_MAIN", extra_info.valid_targets[0])
        print(f"  > Fighter Extra Attack: {event.status_message if event else 'Failed'}")
        result.check(event is not None, "Extra Attack executed")

    # 4. Second action (from Action Surge) - another attack
    actions = get_available_actions(fighter)
    attack_info = next((a for a in actions.entity_actions if a.template_name == "Attack_MELEE_MAIN"), None)
    if attack_info and attack_info.valid_targets:
        event = execute_action(fighter, "Attack_MELEE_MAIN", attack_info.valid_targets[0])
        print(f"  > Fighter second action attack: {event.status_message if event else 'Failed'}")
        result.check(event is not None, "Second action attack executed")

    # 5. Second action's Extra Attack
    actions = get_available_actions(fighter)
    extra_info = next((a for a in actions.entity_actions if a.template_name == "Extra Attack_MELEE_MAIN"), None)
    if extra_info and extra_info.valid_targets:
        event = execute_action(fighter, "Extra Attack_MELEE_MAIN", extra_info.valid_targets[0])
        print(f"  > Fighter second action Extra Attack: {event.status_message if event else 'Failed'}")

    # Deal some damage to fighter to test Second Wind
    fighter.health.add_damage(10)
    hp_before_sw = fighter.get_hp()
    print(f"  > Fighter takes 10 damage (HP: {hp_before_sw})")

    # 6. Use Second Wind (bonus action)
    actions = get_available_actions(fighter)
    sw_info = next((a for a in actions.all_actions if a.template_name == "Second Wind"), None)
    if sw_info and sw_info.valid_targets:
        event = execute_action(fighter, "Second Wind", sw_info.valid_targets[0])
        hp_after_sw = fighter.get_hp()
        print(f"  > Fighter uses Second Wind: HP {hp_before_sw} -> {hp_after_sw}")
        result.check(hp_after_sw > hp_before_sw, "Second Wind healed fighter")

    print("\n  --- End Combat Log ---")
    print(f"\n  Final state:")
    print(f"  Fighter: HP={fighter.get_hp()}")
    print(f"  Skeleton: HP={skeleton.get_hp()}")

    # Check skeleton took damage (attacks should have hit at least once)
    skeleton_damaged = skeleton.get_hp() < skeleton.health.get_max_hit_dices_points(skeleton.ability_scores.constitution.modifier)
    result.check(skeleton_damaged, f"Skeleton took damage (HP now: {skeleton.get_hp()})")

    return result.summary()


def run_all_tests():
    """Run all fighter combat tests."""
    print("=" * 60)
    print("FIGHTER COMBAT SIMULATION TESTS")
    print("=" * 60)

    tests = [
        ("Level 1 Fighter Actions", test_fighter_available_actions_level_1),
        ("Level 5 Fighter Actions", test_fighter_available_actions_level_5),
        ("Second Wind Action", test_second_wind_action),
        ("Action Surge Grants Extra Action", test_action_surge_grants_extra_action),
        ("Extra Attack Workflow", test_extra_attack_workflow),
        ("Full Combat Round", test_full_combat_round),
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
