"""
Test Extra Attack Implementation

Tests:
1. HasAttacked condition applied after action-cost attack
2. ExtraAttack requires HasAttacked as prerequisite
3. ExtraAttack consumes extra_attacks resource
4. Resource recharges at turn start
5. Full combat round: Attack + ExtraAttack = 2 attacks (L5)
6. Fighter L11: Attack + 2 ExtraAttacks = 3 attacks
7. HasAttacked expires after 1 round
"""

from dnd.core.gridmap import get_map
from dnd.entity import Entity
from dnd.monsters.bestiary import create_skeleton, create_goblin
from dnd.actions import Attack
from dnd.actions_functional import setup_standard_actions
from dnd.classes.fighter import ExtraAttackFeature, ExtraAttack
from dnd.core.events import WeaponSlot
from dnd.utils import set_hp, reset_combat_state


def create_fighter_with_extra_attack(name: str, position: tuple, extra_attacks: int = 1) -> Entity:
    """Create a skeleton with Extra Attack feature."""
    fighter = create_skeleton(name=name, position=position)

    # Apply Extra Attack feature
    extra_attack_feature = ExtraAttackFeature(
        source_entity_uuid=fighter.uuid,
        target_entity_uuid=fighter.uuid,
        extra_attacks=extra_attacks
    )
    fighter.add_condition(extra_attack_feature)

    # Setup standard actions (including regular Attack)
    setup_standard_actions(fighter)

    return fighter


def test_has_attacked_applied_after_attack():
    """Test 1: HasAttacked is applied after an action-cost attack."""
    print("\n=== Test 1: HasAttacked applied after attack ===")
    reset_combat_state()
    get_map().create_rectangle(0, 0, 20, 20)

    fighter = create_fighter_with_extra_attack("Fighter", (5, 5))
    target = create_goblin(name="Target", position=(5, 6))
    Entity.update_all_entities_senses(max_distance=20)

    # Before attack: no HasAttacked
    assert "HasAttacked" not in fighter.active_conditions, "Should not have HasAttacked before attacking"
    print(f"Before attack: HasAttacked = {'HasAttacked' in fighter.active_conditions}")

    # Perform attack
    attack = Attack(
        source_entity_uuid=fighter.uuid,
        target_entity_uuid=target.uuid,
        weapon_slot=WeaponSlot.MELEE_MAIN
    )
    event = attack.apply()
    assert event is not None and not event.canceled, "Attack should succeed"

    # After attack: should have HasAttacked
    assert "HasAttacked" in fighter.active_conditions, "Should have HasAttacked after attacking"
    print(f"After attack: HasAttacked = {'HasAttacked' in fighter.active_conditions}")
    print("TEST 1 PASSED")


def test_extra_attack_requires_has_attacked():
    """Test 2: ExtraAttack requires HasAttacked as prerequisite."""
    print("\n=== Test 2: ExtraAttack requires HasAttacked ===")
    reset_combat_state()
    get_map().create_rectangle(0, 0, 20, 20)

    fighter = create_fighter_with_extra_attack("Fighter", (5, 5))
    target = create_goblin(name="Target", position=(5, 6))
    Entity.update_all_entities_senses(max_distance=20)

    # Try Extra Attack without HasAttacked - should fail pre_validate
    extra_attack = ExtraAttack(
        source_entity_uuid=fighter.uuid,
        target_entity_uuid=target.uuid,
        weapon_slot=WeaponSlot.MELEE_MAIN
    )

    # Without HasAttacked, pre_validate should fail
    result = extra_attack.pre_validate()
    print(f"ExtraAttack.pre_validate() without HasAttacked: {result}")
    assert result == False, "ExtraAttack should fail without HasAttacked"

    # Now perform a regular attack to get HasAttacked
    attack = Attack(
        source_entity_uuid=fighter.uuid,
        target_entity_uuid=target.uuid,
        weapon_slot=WeaponSlot.MELEE_MAIN
    )
    attack.apply()

    assert "HasAttacked" in fighter.active_conditions, "Should have HasAttacked after attack"

    # Now ExtraAttack should pass pre_validate
    result = extra_attack.pre_validate()
    print(f"ExtraAttack.pre_validate() with HasAttacked: {result}")
    assert result == True, "ExtraAttack should succeed with HasAttacked"

    print("TEST 2 PASSED")


def test_extra_attack_consumes_resource():
    """Test 3: ExtraAttack consumes extra_attacks resource."""
    print("\n=== Test 3: ExtraAttack consumes resource ===")
    reset_combat_state()
    get_map().create_rectangle(0, 0, 20, 20)

    fighter = create_fighter_with_extra_attack("Fighter", (5, 5), extra_attacks=1)
    target = create_goblin(name="Target", position=(5, 6))
    Entity.update_all_entities_senses(max_distance=20)

    # Check initial resource
    assert fighter.action_economy.has_resource("extra_attacks"), "Should have extra_attacks resource"
    initial = fighter.action_economy.get_resource_current("extra_attacks")
    print(f"Initial extra_attacks: {initial}")
    assert initial == 1, f"Should have 1 extra_attack, got {initial}"

    # Perform regular attack first
    attack = Attack(
        source_entity_uuid=fighter.uuid,
        target_entity_uuid=target.uuid,
        weapon_slot=WeaponSlot.MELEE_MAIN
    )
    attack.apply()

    # Perform extra attack
    extra_attack = ExtraAttack(
        source_entity_uuid=fighter.uuid,
        target_entity_uuid=target.uuid,
        weapon_slot=WeaponSlot.MELEE_MAIN
    )
    event = extra_attack.apply()
    assert event is not None and not event.canceled, "ExtraAttack should succeed"

    # Resource should be consumed
    remaining = fighter.action_economy.get_resource_current("extra_attacks")
    print(f"Remaining extra_attacks after use: {remaining}")
    assert remaining == 0, f"Should have 0 extra_attacks after use, got {remaining}"

    # Should not be able to use another ExtraAttack
    result = extra_attack.pre_validate()
    print(f"ExtraAttack.pre_validate() after resource depleted: {result}")
    assert result == False, "Should not be able to use ExtraAttack when resource is 0"

    print("TEST 3 PASSED")


def test_resource_recharges_at_turn_start():
    """Test 4: extra_attacks resource recharges at turn start."""
    print("\n=== Test 4: Resource recharges at turn start ===")
    reset_combat_state()
    get_map().create_rectangle(0, 0, 20, 20)

    fighter = create_fighter_with_extra_attack("Fighter", (5, 5), extra_attacks=2)
    target = create_goblin(name="Target", position=(5, 6))
    set_hp(target, 200)  # Prevent target dying mid-test
    Entity.update_all_entities_senses(max_distance=20)

    # Use all extra attacks
    # First, regular attack
    attack = Attack(
        source_entity_uuid=fighter.uuid,
        target_entity_uuid=target.uuid,
        weapon_slot=WeaponSlot.MELEE_MAIN
    )
    attack.apply()

    # Use both extra attacks
    for i in range(2):
        extra = ExtraAttack(
            source_entity_uuid=fighter.uuid,
            target_entity_uuid=target.uuid,
            weapon_slot=WeaponSlot.MELEE_MAIN
        )
        event = extra.apply()
        if event and not event.canceled:
            print(f"ExtraAttack {i+1} succeeded")

    remaining = fighter.action_economy.get_resource_current("extra_attacks")
    print(f"After using all: {remaining} extra_attacks")
    assert remaining == 0, "Should have 0 after using all"

    # Simulate turn start
    fighter.action_economy.on_turn_start()

    recharged = fighter.action_economy.get_resource_current("extra_attacks")
    print(f"After turn start: {recharged} extra_attacks")
    assert recharged == 2, f"Should have 2 after recharge, got {recharged}"

    print("TEST 4 PASSED")


def test_full_combat_round_l5():
    """Test 5: Full L5 combat round - Attack + 1 ExtraAttack = 2 attacks."""
    print("\n=== Test 5: Full L5 combat round ===")
    reset_combat_state()
    get_map().create_rectangle(0, 0, 20, 20)

    fighter = create_fighter_with_extra_attack("Fighter", (5, 5), extra_attacks=1)
    target = create_goblin(name="Target", position=(5, 6))
    set_hp(target, 200)  # Prevent target dying mid-test
    Entity.update_all_entities_senses(max_distance=20)

    initial_hp = target.get_hp()
    print(f"Target initial HP: {initial_hp}")
    attacks_made = 0

    # Regular Attack (costs 1 action)
    attack = Attack(
        source_entity_uuid=fighter.uuid,
        target_entity_uuid=target.uuid,
        weapon_slot=WeaponSlot.MELEE_MAIN
    )
    event = attack.apply()
    if event and not event.canceled:
        attacks_made += 1
        outcome = getattr(event, 'attack_outcome', None)
        print(f"Attack 1: {outcome}")

    # Extra Attack (costs 0 actions, 1 resource)
    extra = ExtraAttack(
        source_entity_uuid=fighter.uuid,
        target_entity_uuid=target.uuid,
        weapon_slot=WeaponSlot.MELEE_MAIN
    )
    event = extra.apply()
    if event and not event.canceled:
        attacks_made += 1
        outcome = getattr(event, 'attack_outcome', None)
        print(f"Attack 2 (Extra): {outcome}")

    # Try a third attack - should fail (no more extra_attacks)
    extra2 = ExtraAttack(
        source_entity_uuid=fighter.uuid,
        target_entity_uuid=target.uuid,
        weapon_slot=WeaponSlot.MELEE_MAIN
    )
    can_attack_again = extra2.pre_validate()
    print(f"Can make 3rd attack? {can_attack_again}")
    assert can_attack_again == False, "Should not be able to make 3rd attack at L5"

    print(f"Total attacks made: {attacks_made}")
    assert attacks_made == 2, f"L5 fighter should make 2 attacks, made {attacks_made}"

    print("TEST 5 PASSED")


def test_full_combat_round_l11():
    """Test 6: Full L11 combat round - Attack + 2 ExtraAttacks = 3 attacks."""
    print("\n=== Test 6: Full L11 combat round ===")
    reset_combat_state()
    get_map().create_rectangle(0, 0, 20, 20)

    fighter = create_fighter_with_extra_attack("Fighter", (5, 5), extra_attacks=2)
    target = create_goblin(name="Target", position=(5, 6))
    set_hp(target, 200)  # Prevent target dying mid-test
    Entity.update_all_entities_senses(max_distance=20)

    attacks_made = 0

    # Regular Attack
    attack = Attack(
        source_entity_uuid=fighter.uuid,
        target_entity_uuid=target.uuid,
        weapon_slot=WeaponSlot.MELEE_MAIN
    )
    event = attack.apply()
    if event and not event.canceled:
        attacks_made += 1
        outcome = getattr(event, 'attack_outcome', None)
        print(f"Attack 1: {outcome}")

    # Extra Attack 1
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

    # Extra Attack 2
    extra2 = ExtraAttack(
        source_entity_uuid=fighter.uuid,
        target_entity_uuid=target.uuid,
        weapon_slot=WeaponSlot.MELEE_MAIN
    )
    event = extra2.apply()
    if event and not event.canceled:
        attacks_made += 1
        outcome = getattr(event, 'attack_outcome', None)
        print(f"Attack 3 (Extra): {outcome}")

    # Try a fourth attack - should fail
    extra3 = ExtraAttack(
        source_entity_uuid=fighter.uuid,
        target_entity_uuid=target.uuid,
        weapon_slot=WeaponSlot.MELEE_MAIN
    )
    can_attack_again = extra3.pre_validate()
    print(f"Can make 4th attack? {can_attack_again}")
    assert can_attack_again == False, "Should not be able to make 4th attack at L11"

    print(f"Total attacks made: {attacks_made}")
    assert attacks_made == 3, f"L11 fighter should make 3 attacks, made {attacks_made}"

    print("TEST 6 PASSED")


def test_has_attacked_duration():
    """Test 7: HasAttacked expires after 1 round."""
    print("\n=== Test 7: HasAttacked expires after 1 round ===")
    reset_combat_state()
    get_map().create_rectangle(0, 0, 20, 20)

    fighter = create_fighter_with_extra_attack("Fighter", (5, 5))
    target = create_goblin(name="Target", position=(5, 6))
    Entity.update_all_entities_senses(max_distance=20)

    # Attack to get HasAttacked
    attack = Attack(
        source_entity_uuid=fighter.uuid,
        target_entity_uuid=target.uuid,
        weapon_slot=WeaponSlot.MELEE_MAIN
    )
    attack.apply()

    assert "HasAttacked" in fighter.active_conditions, "Should have HasAttacked"
    print(f"Has HasAttacked: True")

    # Progress the condition (simulates next turn)
    # Note: progress() returns True if expired, but caller must remove from entity
    has_attacked = fighter.active_conditions.get("HasAttacked")
    if has_attacked:
        expired = has_attacked.progress()
        print(f"After progress: expired={expired}")
        assert expired == True, "HasAttacked should expire after 1 round"

        # In real game loop, expired conditions are removed by the encounter/turn system
        # Here we manually remove it as the caller
        if expired:
            fighter.remove_condition("HasAttacked")

    # Should be removed
    assert "HasAttacked" not in fighter.active_conditions, "HasAttacked should be removed after expiration"
    print(f"Has HasAttacked after removal: {'HasAttacked' in fighter.active_conditions}")

    print("TEST 7 PASSED")


if __name__ == "__main__":
    print("=" * 60)
    print("EXTRA ATTACK IMPLEMENTATION TESTS")
    print("=" * 60)

    test_has_attacked_applied_after_attack()
    test_extra_attack_requires_has_attacked()
    test_extra_attack_consumes_resource()
    test_resource_recharges_at_turn_start()
    test_full_combat_round_l5()
    test_full_combat_round_l11()
    test_has_attacked_duration()

    print("\n" + "=" * 60)
    print("ALL TESTS PASSED!")
    print("=" * 60)
