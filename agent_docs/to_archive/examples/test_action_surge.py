"""
Test Action Surge Implementation

Tests:
1. ActionSurgeFeature adds resource (1/1) and action template
2. Basic usage - ActionSurge grants +1 action (2 total)
3. Resource not available - ActionSurge fails pre_validate
4. Once-per-turn enforcement - HasUsedActionSurge blocks second use
5. Short rest recharge - resource restores after short rest
6. Level 17 (2 uses per rest) - can use twice across different turns
7. Integration with Extra Attack - 4 attacks with L5 Fighter + Action Surge
"""

from dnd.core.gridmap import get_map
from dnd.entity import Entity
from dnd.monsters.bestiary import create_skeleton, create_goblin
from dnd.actions import Attack
from dnd.actions_functional import setup_standard_actions
from dnd.classes.fighter import ExtraAttackFeature, ActionSurgeFeature, ExtraAttack, ActionSurge
from dnd.core.events import WeaponSlot
from dnd.utils import force_attack_miss, reset_combat_state


def setup_test():
    """Reset all combat state and create a clean map."""
    reset_combat_state()
    get_map().create_rectangle(0, 0, 20, 20)


def create_fighter_with_action_surge(name: str, position: tuple, num_uses: int = 1) -> Entity:
    """Create a skeleton with Action Surge feature."""
    fighter = create_skeleton(name=name, position=position)

    # Setup standard actions FIRST (this clears registered_actions)
    setup_standard_actions(fighter)

    # Apply Action Surge feature (registers Action Surge action)
    action_surge_feature = ActionSurgeFeature(
        source_entity_uuid=fighter.uuid,
        target_entity_uuid=fighter.uuid,
        num_uses=num_uses
    )
    fighter.add_condition(action_surge_feature)

    return fighter


def create_fighter_with_both_features(name: str, position: tuple, extra_attacks: int = 1, action_surge_uses: int = 1) -> Entity:
    """Create a skeleton with both Extra Attack and Action Surge features."""
    fighter = create_skeleton(name=name, position=position)

    # Setup standard actions FIRST (this clears registered_actions)
    setup_standard_actions(fighter)

    # Apply Extra Attack feature (registers ExtraAttack action templates)
    extra_attack_feature = ExtraAttackFeature(
        source_entity_uuid=fighter.uuid,
        target_entity_uuid=fighter.uuid,
        extra_attacks=extra_attacks
    )
    fighter.add_condition(extra_attack_feature)

    # Apply Action Surge feature (registers Action Surge action)
    action_surge_feature = ActionSurgeFeature(
        source_entity_uuid=fighter.uuid,
        target_entity_uuid=fighter.uuid,
        num_uses=action_surge_uses
    )
    fighter.add_condition(action_surge_feature)

    return fighter


def test_feature_setup():
    """Test 1: ActionSurgeFeature adds resource and action template."""
    print("\n=== Test 1: Feature setup ===")
    setup_test()

    fighter = create_fighter_with_action_surge("Fighter", (5, 5))
    Entity.update_all_entities_senses(max_distance=20)

    # Check resource exists
    assert fighter.action_economy.has_resource("action_surge"), "Should have action_surge resource"
    current = fighter.action_economy.get_resource_current("action_surge")
    resource = fighter.action_economy.resources.get("action_surge")
    maximum = resource.maximum if resource else 0
    print(f"action_surge resource: {current}/{maximum}")
    assert current == 1, f"Current should be 1, got {current}"
    assert maximum == 1, f"Maximum should be 1, got {maximum}"

    # Check action template registered
    action_names = [a.name for a in fighter.registered_actions]
    assert "Action Surge" in action_names, f"Should have Action Surge action template, found: {action_names}"
    print(f"Action template registered: True")

    print("TEST 1 PASSED")


def test_basic_usage():
    """Test 2: ActionSurge grants +1 action."""
    print("\n=== Test 2: Basic usage - grants +1 action ===")
    setup_test()

    fighter = create_fighter_with_action_surge("Fighter", (5, 5))
    Entity.update_all_entities_senses(max_distance=20)

    # Reset action economy for clean test
    fighter.action_economy.reset_all_costs()
    initial_actions = fighter.action_economy.actions.normalized_score
    print(f"Initial actions: {initial_actions}")
    assert initial_actions == 1, f"Should have 1 action, got {initial_actions}"

    # Before: no ActionSurging condition
    assert "ActionSurging" not in fighter.active_conditions, "Should not have ActionSurging before use"

    # Use Action Surge
    action_surge = ActionSurge(
        source_entity_uuid=fighter.uuid
    )
    event = action_surge.apply()
    assert event is not None and not event.canceled, f"Action Surge should succeed: {event.status_message if event else 'None'}"
    print(f"Action Surge result: {event.status_message}")

    # After: +1 action and ActionSurging condition (serves as both effect and marker)
    final_actions = fighter.action_economy.actions.normalized_score
    print(f"Actions after Action Surge: {final_actions}")
    assert final_actions == 2, f"Should have 2 actions after Action Surge, got {final_actions}"

    assert "ActionSurging" in fighter.active_conditions, "Should have ActionSurging condition"

    # Resource should be consumed
    remaining = fighter.action_economy.get_resource_current("action_surge")
    print(f"Remaining action_surge resource: {remaining}")
    assert remaining == 0, f"Should have 0 action_surge after use, got {remaining}"

    print("TEST 2 PASSED")


def test_resource_not_available():
    """Test 3: ActionSurge fails when resource is 0."""
    print("\n=== Test 3: Resource not available ===")
    setup_test()

    fighter = create_fighter_with_action_surge("Fighter", (5, 5))
    Entity.update_all_entities_senses(max_distance=20)

    # Manually set resource to 0
    fighter.action_economy.resources["action_surge"].current = 0

    # Try Action Surge - should fail pre_validate
    action_surge = ActionSurge(
        source_entity_uuid=fighter.uuid
    )
    result = action_surge.pre_validate()
    print(f"ActionSurge.pre_validate() with resource=0: {result}")
    assert result == False, "ActionSurge should fail when resource is 0"

    print("TEST 3 PASSED")


def test_once_per_turn_enforcement():
    """Test 4: ActionSurging blocks second use even if resource is refreshed."""
    print("\n=== Test 4: Once-per-turn enforcement ===")
    setup_test()

    fighter = create_fighter_with_action_surge("Fighter", (5, 5), num_uses=2)  # Give 2 uses for test
    Entity.update_all_entities_senses(max_distance=20)

    # Use Action Surge
    action_surge = ActionSurge(source_entity_uuid=fighter.uuid)
    event = action_surge.apply()
    assert event is not None and not event.canceled, "First Action Surge should succeed"
    print(f"First Action Surge: {event.status_message}")

    # Manually refresh resource (simulating magic item)
    fighter.action_economy.resources["action_surge"].current = 1
    current = fighter.action_economy.get_resource_current("action_surge")
    print(f"Resource after magic refresh: {current}")

    # ActionSurging should be present (serves as both effect and once-per-turn marker)
    assert "ActionSurging" in fighter.active_conditions, "Should have ActionSurging condition"

    # Try second Action Surge - should fail due to once-per-turn limit
    action_surge2 = ActionSurge(source_entity_uuid=fighter.uuid)
    result = action_surge2.pre_validate()
    print(f"ActionSurge.pre_validate() with ActionSurging present: {result}")
    assert result == False, "Second ActionSurge should fail due to once-per-turn limit"

    print("TEST 4 PASSED")


def test_short_rest_recharge():
    """Test 5: action_surge resource recharges on short rest."""
    print("\n=== Test 5: Short rest recharge ===")
    setup_test()

    fighter = create_fighter_with_action_surge("Fighter", (5, 5))
    Entity.update_all_entities_senses(max_distance=20)

    # Use Action Surge
    action_surge = ActionSurge(source_entity_uuid=fighter.uuid)
    event = action_surge.apply()
    assert event is not None and not event.canceled, "Action Surge should succeed"

    remaining = fighter.action_economy.get_resource_current("action_surge")
    print(f"After use: {remaining} action_surge")
    assert remaining == 0, "Should have 0 after use"

    # Take a short rest
    fighter.action_economy.on_short_rest()

    restored = fighter.action_economy.get_resource_current("action_surge")
    print(f"After short rest: {restored} action_surge")
    assert restored == 1, f"Should have 1 after short rest, got {restored}"

    print("TEST 5 PASSED")


def test_level_17_two_uses():
    """Test 6: Level 17 - can use twice across different turns."""
    print("\n=== Test 6: Level 17 (2 uses per rest) ===")
    setup_test()

    fighter = create_fighter_with_action_surge("Fighter", (5, 5), num_uses=2)
    Entity.update_all_entities_senses(max_distance=20)

    initial = fighter.action_economy.get_resource_current("action_surge")
    print(f"Initial action_surge: {initial}")
    assert initial == 2, f"Should have 2 at L17, got {initial}"

    # Turn 1: Use Action Surge
    action_surge1 = ActionSurge(source_entity_uuid=fighter.uuid)
    event1 = action_surge1.apply()
    assert event1 is not None and not event1.canceled, "First Action Surge should succeed"
    print(f"Turn 1: Used Action Surge")

    remaining = fighter.action_economy.get_resource_current("action_surge")
    print(f"Resource after turn 1: {remaining}")
    assert remaining == 1, "Should have 1 remaining"

    # Simulate turn end: ActionSurging expires
    surging = fighter.active_conditions.get("ActionSurging")
    if surging:
        expired = surging.progress()
        if expired:
            fighter.remove_condition("ActionSurging")

    assert "ActionSurging" not in fighter.active_conditions, "ActionSurging should expire"
    print(f"Turn 2: ActionSurging expired")

    # Turn 2: Use Action Surge again
    action_surge2 = ActionSurge(source_entity_uuid=fighter.uuid)
    event2 = action_surge2.apply()
    assert event2 is not None and not event2.canceled, "Second Action Surge should succeed"
    print(f"Turn 2: Used Action Surge")

    remaining = fighter.action_economy.get_resource_current("action_surge")
    print(f"Resource after turn 2: {remaining}")
    assert remaining == 0, "Should have 0 remaining"

    # Can't use again until rest
    action_surge3 = ActionSurge(source_entity_uuid=fighter.uuid)
    result = action_surge3.pre_validate()
    print(f"Can use again? {result}")
    assert result == False, "Should not be able to use again until rest"

    print("TEST 6 PASSED")


def test_integration_with_extra_attack():
    """Test 7: Integration - L5 Fighter + Action Surge = 4 attacks."""
    print("\n=== Test 7: Integration with Extra Attack ===")
    setup_test()

    # Create L5 Fighter with Extra Attack (1 extra) and Action Surge
    fighter = create_fighter_with_both_features("Fighter", (5, 5), extra_attacks=1, action_surge_uses=1)
    target = create_goblin(name="Target", position=(5, 6))
    Entity.update_all_entities_senses(max_distance=20)

    # Force all attacks to miss so target survives all 4 attacks
    force_attack_miss(fighter)

    # Reset action economy
    fighter.action_economy.reset_all_costs()
    # Also trigger turn start to set up resources
    fighter.action_economy.on_turn_start()

    attacks_made = 0

    print("\n--- First Attack Action ---")
    # Attack 1 (Action #1)
    attack1 = Attack(
        source_entity_uuid=fighter.uuid,
        target_entity_uuid=target.uuid,
        weapon_slot=WeaponSlot.MELEE_MAIN
    )
    event = attack1.apply()
    if event and not event.canceled:
        attacks_made += 1
        outcome = getattr(event, 'attack_outcome', None)
        print(f"Attack 1: {outcome}")

    # Extra Attack 1 (uses extra_attacks resource, not action)
    extra1 = ExtraAttack(
        source_entity_uuid=fighter.uuid,
        target_entity_uuid=target.uuid,
        weapon_slot=WeaponSlot.MELEE_MAIN
    )
    event = extra1.apply()
    if event and not event.canceled:
        attacks_made += 1
        outcome = getattr(event, 'attack_outcome', None)
        print(f"Attack 2 (Extra): {outcome}")

    print(f"Attacks after first Attack action: {attacks_made}")
    actions_remaining = fighter.action_economy.actions.normalized_score
    print(f"Actions remaining: {actions_remaining}")

    print("\n--- Action Surge ---")
    # Use Action Surge to get another action
    action_surge = ActionSurge(source_entity_uuid=fighter.uuid)
    event = action_surge.apply()
    assert event is not None and not event.canceled, f"Action Surge should succeed: {event.status_message if event else 'None'}"
    print(f"Action Surge used!")

    actions_after_surge = fighter.action_economy.actions.normalized_score
    print(f"Actions after Action Surge: {actions_after_surge}")

    print("\n--- Second Attack Action ---")
    # Attack 3 (Action #2 from Action Surge)
    attack2 = Attack(
        source_entity_uuid=fighter.uuid,
        target_entity_uuid=target.uuid,
        weapon_slot=WeaponSlot.MELEE_MAIN
    )
    event = attack2.apply()
    if event and not event.canceled:
        attacks_made += 1
        outcome = getattr(event, 'attack_outcome', None)
        print(f"Attack 3: {outcome}")

    # Check extra_attacks resource (should have been refreshed by second Attack action)
    extra_attacks_current = fighter.action_economy.get_resource_current("extra_attacks")
    print(f"extra_attacks resource: {extra_attacks_current}")

    # Extra Attack 2 (if resource available)
    if extra_attacks_current > 0:
        extra2 = ExtraAttack(
            source_entity_uuid=fighter.uuid,
            target_entity_uuid=target.uuid,
            weapon_slot=WeaponSlot.MELEE_MAIN
        )
        event = extra2.apply()
        if event and not event.canceled:
            attacks_made += 1
            outcome = getattr(event, 'attack_outcome', None)
            print(f"Attack 4 (Extra): {outcome}")

    print(f"\nTotal attacks made: {attacks_made}")
    # L5 Fighter with Action Surge: 2 actions x 2 attacks each = 4 attacks
    assert attacks_made == 4, f"L5 Fighter with Action Surge should make 4 attacks, made {attacks_made}"

    print("TEST 7 PASSED")


if __name__ == "__main__":
    print("=" * 60)
    print("ACTION SURGE IMPLEMENTATION TESTS")
    print("=" * 60)

    test_feature_setup()
    test_basic_usage()
    test_resource_not_available()
    test_once_per_turn_enforcement()
    test_short_rest_recharge()
    test_level_17_two_uses()
    test_integration_with_extra_attack()

    print("\n" + "=" * 60)
    print("ALL TESTS PASSED!")
    print("=" * 60)
