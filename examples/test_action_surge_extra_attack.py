"""
Test Action Surge + Extra Attack Interaction

Tests that Extra Attack works correctly with Action Surge, granting
additional extra attacks for each Attack action taken.

Expected behavior:
- Level 5 Fighter (1 extra attack) + Action Surge = 4 attacks total
- Level 11 Fighter (2 extra attacks) + Action Surge = 6 attacks total
"""

from dnd.core.gridmap import get_map, reset_map
from dnd.entity import Entity
from dnd.monsters.bestiary import create_skeleton, create_goblin
from dnd.actions import Attack
from dnd.classes.fighter import ExtraAttackFeature, ExtraAttack
from dnd.core.events import WeaponSlot, EventQueue
from dnd.core.modifiers import NumericalModifier


def setup_test():
    """Reset entity registries, event queue, and create a clean map."""
    Entity._entity_registry.clear()
    Entity._entity_by_position.clear()
    reset_map()

    # Clear EventQueue handlers
    EventQueue._event_handlers.clear()
    EventQueue._event_handlers_by_trigger.clear()
    EventQueue._event_handlers_by_simple_trigger.clear()
    EventQueue._event_handlers_by_source_entity_uuid.clear()

    # Clear events
    EventQueue._events_by_lineage.clear()
    EventQueue._events_by_uuid.clear()
    EventQueue._events_by_type.clear()
    EventQueue._events_by_timestamp.clear()
    EventQueue._events_by_phase.clear()
    EventQueue._events_by_source.clear()
    EventQueue._events_by_target.clear()
    EventQueue._all_events.clear()

    grid = get_map()
    grid.create_rectangle(0, 0, 20, 20)


def create_fighter_with_extra_attack(name: str, position: tuple, extra_attacks: int = 1) -> Entity:
    """Create a skeleton with Extra Attack feature."""
    # Note: create_skeleton already calls setup_standard_actions internally
    fighter = create_skeleton(name=name, position=position)

    # Apply Extra Attack feature
    extra_attack_feature = ExtraAttackFeature(
        source_entity_uuid=fighter.uuid,
        target_entity_uuid=fighter.uuid,
        extra_attacks=extra_attacks
    )
    fighter.add_condition(extra_attack_feature)

    # Don't call setup_standard_actions again - create_skeleton already did it
    return fighter


def simulate_action_surge(entity: Entity):
    """Simulate Action Surge by adding +1 to actions."""
    entity.action_economy.actions.self_static.add_value_modifier(
        NumericalModifier.create(
            source_entity_uuid=entity.uuid,
            name="Action Surge",
            value=1
        )
    )


def test_normal_turn_two_attacks():
    """Test Level 5 Fighter normal turn: 2 attacks (1 regular + 1 extra)."""
    print("\n=== Test 1: Normal Turn - 2 Attacks (Level 5) ===")
    setup_test()

    fighter = create_fighter_with_extra_attack("Fighter", (5, 5), extra_attacks=1)
    target = create_goblin(name="Target", position=(5, 6))
    Entity.update_all_entities_senses(max_distance=20)

    attacks_made = 0

    # First attack (action-cost)
    attack = Attack(
        source_entity_uuid=fighter.uuid,
        target_entity_uuid=target.uuid,
        weapon_slot=WeaponSlot.MELEE_MAIN
    )
    result = attack.apply()
    if result and not result.canceled:
        attacks_made += 1
        print(f"  Attack 1 (action): Done")

    # Check extra attacks available
    extra_resource = fighter.action_economy.resources.get("extra_attacks")
    print(f"  Extra attacks available: {extra_resource.current if extra_resource else 0}")

    # Extra attack
    if extra_resource and extra_resource.current > 0:
        extra = ExtraAttack(
            source_entity_uuid=fighter.uuid,
            target_entity_uuid=target.uuid,
            weapon_slot=WeaponSlot.MELEE_MAIN
        )
        result = extra.apply()
        if result and not result.canceled:
            attacks_made += 1
            print(f"  Extra Attack 1: Done")

    print(f"  Total attacks: {attacks_made}")
    assert attacks_made == 2, f"Should make 2 attacks, made {attacks_made}"
    print("  PASSED")
    return True


def test_action_surge_interleaved():
    """Test Action Surge interleaved: Attack + Extra + Surge + Attack + Extra = 4."""
    print("\n=== Test 2: Action Surge Interleaved - 4 Attacks ===")
    setup_test()

    fighter = create_fighter_with_extra_attack("Fighter", (5, 5), extra_attacks=1)
    target = create_goblin(name="Target", position=(5, 6))
    Entity.update_all_entities_senses(max_distance=20)

    attacks_made = 0
    extra_resource = fighter.action_economy.resources.get("extra_attacks")

    # First Attack action
    attack1 = Attack(
        source_entity_uuid=fighter.uuid,
        target_entity_uuid=target.uuid,
        weapon_slot=WeaponSlot.MELEE_MAIN
    )
    result = attack1.apply()
    if result and not result.canceled:
        attacks_made += 1
        print(f"  Attack 1 (action): Done")

    # First Extra Attack
    print(f"  Extra attacks after 1st Attack: {extra_resource.current if extra_resource else 0}")
    if extra_resource and extra_resource.current > 0:
        extra1 = ExtraAttack(
            source_entity_uuid=fighter.uuid,
            target_entity_uuid=target.uuid,
            weapon_slot=WeaponSlot.MELEE_MAIN
        )
        result = extra1.apply()
        if result and not result.canceled:
            attacks_made += 1
            print(f"  Extra Attack 1: Done")

    # Action Surge
    print("  === Action Surge ===")
    simulate_action_surge(fighter)

    # Second Attack action - should grant more extra attacks
    attack2 = Attack(
        source_entity_uuid=fighter.uuid,
        target_entity_uuid=target.uuid,
        weapon_slot=WeaponSlot.MELEE_MAIN
    )
    result = attack2.apply()
    if result and not result.canceled:
        attacks_made += 1
        print(f"  Attack 2 (action): Done")

    # Check extra attacks after second Attack action
    print(f"  Extra attacks after 2nd Attack: {extra_resource.current if extra_resource else 0}")

    # Second Extra Attack
    if extra_resource and extra_resource.current > 0:
        extra2 = ExtraAttack(
            source_entity_uuid=fighter.uuid,
            target_entity_uuid=target.uuid,
            weapon_slot=WeaponSlot.MELEE_MAIN
        )
        result = extra2.apply()
        if result and not result.canceled:
            attacks_made += 1
            print(f"  Extra Attack 2: Done")

    print(f"  Total attacks: {attacks_made}")
    assert attacks_made == 4, f"Should make 4 attacks with Action Surge, made {attacks_made}"
    print("  PASSED")
    return True


def test_action_surge_first():
    """Test Action Surge used first: Surge + Attack + Attack + Extras = 4."""
    print("\n=== Test 3: Action Surge First - 4 Attacks ===")
    setup_test()

    fighter = create_fighter_with_extra_attack("Fighter", (5, 5), extra_attacks=1)
    target = create_goblin(name="Target", position=(5, 6))
    Entity.update_all_entities_senses(max_distance=20)

    attacks_made = 0
    extra_resource = fighter.action_economy.resources.get("extra_attacks")

    # Action Surge FIRST
    print("  === Action Surge (used first) ===")
    simulate_action_surge(fighter)

    # First Attack action
    attack1 = Attack(
        source_entity_uuid=fighter.uuid,
        target_entity_uuid=target.uuid,
        weapon_slot=WeaponSlot.MELEE_MAIN
    )
    result = attack1.apply()
    if result and not result.canceled:
        attacks_made += 1
        print(f"  Attack 1 (action): Done")

    print(f"  Extra attacks after 1st Attack: {extra_resource.current if extra_resource else 0}")

    # Second Attack action
    attack2 = Attack(
        source_entity_uuid=fighter.uuid,
        target_entity_uuid=target.uuid,
        weapon_slot=WeaponSlot.MELEE_MAIN
    )
    result = attack2.apply()
    if result and not result.canceled:
        attacks_made += 1
        print(f"  Attack 2 (action): Done")

    print(f"  Extra attacks after 2nd Attack: {extra_resource.current if extra_resource else 0}")

    # Use all extra attacks
    while extra_resource and extra_resource.current > 0:
        extra = ExtraAttack(
            source_entity_uuid=fighter.uuid,
            target_entity_uuid=target.uuid,
            weapon_slot=WeaponSlot.MELEE_MAIN
        )
        result = extra.apply()
        if result and not result.canceled:
            attacks_made += 1
            print(f"  Extra Attack: Done (remaining: {extra_resource.current})")
        else:
            break

    print(f"  Total attacks: {attacks_made}")
    assert attacks_made == 4, f"Should make 4 attacks, made {attacks_made}"
    print("  PASSED")
    return True


def test_level_11_with_action_surge():
    """Test Level 11 Fighter (2 extra attacks) + Action Surge = 6 attacks."""
    print("\n=== Test 4: Level 11 + Action Surge - 6 Attacks ===")
    setup_test()

    fighter = create_fighter_with_extra_attack("Fighter", (5, 5), extra_attacks=2)  # Level 11
    target = create_goblin(name="Target", position=(5, 6))
    Entity.update_all_entities_senses(max_distance=20)

    attacks_made = 0
    extra_resource = fighter.action_economy.resources.get("extra_attacks")

    # First Attack action
    attack1 = Attack(
        source_entity_uuid=fighter.uuid,
        target_entity_uuid=target.uuid,
        weapon_slot=WeaponSlot.MELEE_MAIN
    )
    result = attack1.apply()
    if result and not result.canceled:
        attacks_made += 1
        print(f"  Attack 1 (action): Done")

    # First set of Extra Attacks (should be 2)
    print(f"  Extra attacks available: {extra_resource.current if extra_resource else 0}")
    while extra_resource and extra_resource.current > 0:
        extra = ExtraAttack(
            source_entity_uuid=fighter.uuid,
            target_entity_uuid=target.uuid,
            weapon_slot=WeaponSlot.MELEE_MAIN
        )
        result = extra.apply()
        if result and not result.canceled:
            attacks_made += 1
        else:
            break

    print(f"  After first Attack action: {attacks_made} attacks")

    # Action Surge
    print("  === Action Surge ===")
    simulate_action_surge(fighter)

    # Second Attack action
    attack2 = Attack(
        source_entity_uuid=fighter.uuid,
        target_entity_uuid=target.uuid,
        weapon_slot=WeaponSlot.MELEE_MAIN
    )
    result = attack2.apply()
    if result and not result.canceled:
        attacks_made += 1
        print(f"  Attack 2 (action): Done")

    print(f"  Extra attacks after 2nd Attack: {extra_resource.current if extra_resource else 0}")

    # Second set of Extra Attacks (should add 2 more)
    while extra_resource and extra_resource.current > 0:
        extra = ExtraAttack(
            source_entity_uuid=fighter.uuid,
            target_entity_uuid=target.uuid,
            weapon_slot=WeaponSlot.MELEE_MAIN
        )
        result = extra.apply()
        if result and not result.canceled:
            attacks_made += 1
        else:
            break

    print(f"  Total attacks: {attacks_made}")
    assert attacks_made == 6, f"Level 11 + Surge should make 6 attacks, made {attacks_made}"
    print("  PASSED")
    return True


def main():
    print("=" * 60)
    print("ACTION SURGE + EXTRA ATTACK TESTS")
    print("=" * 60)

    results = []
    results.append(("Normal Turn (2 attacks)", test_normal_turn_two_attacks()))
    results.append(("Action Surge Interleaved", test_action_surge_interleaved()))
    results.append(("Action Surge First", test_action_surge_first()))
    results.append(("Level 11 + Surge (6)", test_level_11_with_action_surge()))

    print("\n" + "=" * 60)
    print("RESULTS:")
    print("=" * 60)
    for name, passed in results:
        status = "PASSED" if passed else "FAILED"
        print(f"  {name}: {status}")

    all_passed = all(r[1] for r in results)
    print(f"\nOverall: {'ALL TESTS PASSED' if all_passed else 'SOME TESTS FAILED'}")
    return 0 if all_passed else 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
