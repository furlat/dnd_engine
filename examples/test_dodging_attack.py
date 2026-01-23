"""
Test that attacking a Dodging target actually rolls with disadvantage.
"""

from dnd.monsters.bestiary import create_goblin, create_skeleton
from dnd.conditions import Dodging
from dnd.actions import Attack
from dnd.blocks.equipment import WeaponSlot
from dnd.entity import Entity
from dnd.core.values import AdvantageStatus


def reset_entities():
    """Clear entity registries for a fresh test."""
    Entity._entity_registry.clear()
    Entity._entity_by_position.clear()


def test_attack_vs_dodging():
    """Test that an actual attack against a dodging target has disadvantage."""
    print("=" * 70)
    print(" TEST: ATTACK VS DODGING TARGET")
    print("=" * 70)

    reset_entities()

    # Create attacker and target at melee range
    attacker = create_goblin(name="Attacker", position=(0, 0))
    target = create_skeleton(name="Target", position=(1, 0))
    Entity.update_all_entities_senses()

    print(f"\nSetup: {attacker.name} at (0,0), {target.name} at (1,0)")

    # Apply Dodging to target
    dodging = Dodging(source_entity_uuid=target.uuid, target_entity_uuid=target.uuid)
    target.add_condition(dodging)
    print(f"Applied Dodging condition to {target.name}")
    print(f"Target conditions: {list(target.active_conditions.keys())}")

    # Create and execute attack
    attack = Attack(
        source_entity_uuid=attacker.uuid,
        target_entity_uuid=target.uuid,
        weapon_slot=WeaponSlot.MELEE_MAIN,
        name=f"{attacker.name} attacks {target.name}"
    )

    print(f"\nExecuting attack...")
    event = attack.apply()

    # Check the dice roll
    dice_roll = getattr(event, 'dice_roll', None)
    attack_bonus_mv = getattr(event, 'attack_bonus', None)

    print(f"\n--- RESULTS ---")

    if dice_roll:
        print(f"Dice roll results: {dice_roll.results}")
        print(f"Dice roll total: {dice_roll.total}")
        print(f"Dice roll bonus: {dice_roll.bonus}")
        print(f"Advantage status: {dice_roll.advantage_status}")

        # Check if two dice were rolled (disadvantage)
        num_dice = len(dice_roll.results) if isinstance(dice_roll.results, list) else 1
        print(f"Number of d20s rolled: {num_dice}")

        if dice_roll.advantage_status == AdvantageStatus.DISADVANTAGE:
            print("\n[PASS] Attack has DISADVANTAGE as expected!")
            return True
        else:
            print(f"\n[FAIL] Attack should have DISADVANTAGE but has {dice_roll.advantage_status}")
            return False
    else:
        print("[FAIL] No dice roll found in event")
        return False


def test_attack_without_dodging():
    """Control test - attack without dodging should be normal."""
    print("\n" + "=" * 70)
    print(" CONTROL TEST: ATTACK WITHOUT DODGING")
    print("=" * 70)

    reset_entities()

    attacker = create_goblin(name="Attacker", position=(0, 0))
    target = create_skeleton(name="Target", position=(1, 0))
    Entity.update_all_entities_senses()

    print(f"\nSetup: {attacker.name} at (0,0), {target.name} at (1,0)")
    print(f"Target conditions: {list(target.active_conditions.keys())}")

    attack = Attack(
        source_entity_uuid=attacker.uuid,
        target_entity_uuid=target.uuid,
        weapon_slot=WeaponSlot.MELEE_MAIN,
        name=f"{attacker.name} attacks {target.name}"
    )

    print(f"\nExecuting attack...")
    event = attack.apply()

    dice_roll = getattr(event, 'dice_roll', None)

    print(f"\n--- RESULTS ---")

    if dice_roll:
        print(f"Dice roll results: {dice_roll.results}")
        print(f"Advantage status: {dice_roll.advantage_status}")

        num_dice = len(dice_roll.results) if isinstance(dice_roll.results, list) else 1
        print(f"Number of d20s rolled: {num_dice}")

        if dice_roll.advantage_status == AdvantageStatus.NONE:
            print("\n[PASS] Attack has NO advantage/disadvantage as expected!")
            return True
        else:
            print(f"\n[FAIL] Attack should have NONE but has {dice_roll.advantage_status}")
            return False
    else:
        print("[FAIL] No dice roll found in event")
        return False


if __name__ == "__main__":
    result1 = test_attack_without_dodging()  # Control
    result2 = test_attack_vs_dodging()       # Test

    print("\n" + "=" * 70)
    print(" SUMMARY")
    print("=" * 70)
    print(f"Control (no dodging): {'PASS' if result1 else 'FAIL'}")
    print(f"Test (with dodging):  {'PASS' if result2 else 'FAIL'}")

    if result1 and result2:
        print("\nALL TESTS PASSED!")
    else:
        print("\nSOME TESTS FAILED!")
