"""
Test Two-Weapon Fighting rules:
1. Only LIGHT weapons can be equipped in off-hand slots
2. Off-hand attacks cost a bonus action (not an action)
3. Off-hand attacks don't add ability modifier to damage
"""

from dnd.monsters.bestiary import create_goblin
from dnd.blocks.equipment import Weapon, WeaponProperty, WeaponSlot
from dnd.core.modifiers import DamageType
from dnd.core.values import ModifiableValue
from dnd.core.events import RangeType, Range
from dnd.entity import Entity
from dnd.actions import Attack


def reset_entities():
    """Clear entity registries for a fresh test."""
    Entity._entity_registry.clear()
    Entity._entity_by_position.clear()


def create_light_dagger(source_id):
    """Create a LIGHT dagger for off-hand use."""
    return Weapon(
        source_entity_uuid=source_id,
        name="Light Dagger",
        damage_dice=4,
        dice_numbers=1,
        damage_type=DamageType.PIERCING,
        properties=[WeaponProperty.LIGHT, WeaponProperty.FINESSE],
        range=Range(type=RangeType.REACH, normal=5),
        attack_bonus=ModifiableValue.create(
            source_entity_uuid=source_id,
            base_value=0,
            value_name="Attack Bonus"
        )
    )


def create_heavy_sword(source_id):
    """Create a non-LIGHT sword that should be rejected from off-hand."""
    return Weapon(
        source_entity_uuid=source_id,
        name="Heavy Sword",
        damage_dice=8,
        dice_numbers=1,
        damage_type=DamageType.SLASHING,
        properties=[],  # NOT LIGHT
        range=Range(type=RangeType.REACH, normal=5),
        attack_bonus=ModifiableValue.create(
            source_entity_uuid=source_id,
            base_value=0,
            value_name="Attack Bonus"
        )
    )


def test_light_weapon_requirement():
    """Test that only LIGHT weapons can be equipped in off-hand slots."""
    print("=" * 70)
    print(" TEST 1: LIGHT weapon requirement for off-hand slots")
    print("=" * 70)

    reset_entities()
    goblin = create_goblin(name="Goblin", position=(0, 0))

    heavy_sword = create_heavy_sword(goblin.uuid)
    light_dagger = create_light_dagger(goblin.uuid)

    # Heavy weapon should fail in off-hand
    print("\nAttempting to equip heavy sword in MELEE_OFF...")
    try:
        goblin.equipment.equip(heavy_sword, WeaponSlot.MELEE_OFF)
        print("[FAIL] Heavy sword was equipped (should have been rejected)")
        result1 = False
    except ValueError as e:
        print(f"[PASS] Heavy sword rejected: {e}")
        result1 = True

    # Light weapon should succeed in off-hand
    print("\nAttempting to equip light dagger in MELEE_OFF...")
    try:
        goblin.equipment.equip(light_dagger, WeaponSlot.MELEE_OFF)
        print("[PASS] Light dagger equipped successfully")
        result2 = True
    except ValueError as e:
        print(f"[FAIL] Light dagger was rejected: {e}")
        result2 = False

    return result1 and result2


def test_off_hand_costs_bonus_action():
    """Test that off-hand attacks cost a bonus action instead of an action."""
    print("\n" + "=" * 70)
    print(" TEST 2: Off-hand attack costs BONUS ACTION")
    print("=" * 70)

    reset_entities()
    attacker = create_goblin(name="Attacker", position=(0, 0))
    target = create_goblin(name="Target", position=(1, 0))

    # Equip light dagger in off-hand
    dagger = create_light_dagger(attacker.uuid)
    attacker.equipment.equip(dagger, WeaponSlot.MELEE_OFF)
    Entity.update_all_entities_senses()

    # Main hand attack
    main_attack = Attack(
        source_entity_uuid=attacker.uuid,
        target_entity_uuid=target.uuid,
        weapon_slot=WeaponSlot.MELEE_MAIN,
        name="Main hand attack"
    )
    print(f"\nMain hand attack cost: {main_attack.costs[0].cost_type} = {main_attack.costs[0].cost}")
    result1 = main_attack.costs[0].cost_type == "actions"
    if result1:
        print("[PASS] Main hand costs an action")
    else:
        print(f"[FAIL] Main hand should cost 'actions', got '{main_attack.costs[0].cost_type}'")

    # Off-hand attack
    off_attack = Attack(
        source_entity_uuid=attacker.uuid,
        target_entity_uuid=target.uuid,
        weapon_slot=WeaponSlot.MELEE_OFF,
        name="Off hand attack"
    )
    print(f"Off-hand attack cost: {off_attack.costs[0].cost_type} = {off_attack.costs[0].cost}")
    result2 = off_attack.costs[0].cost_type == "bonus_actions"
    if result2:
        print("[PASS] Off-hand costs a bonus action")
    else:
        print(f"[FAIL] Off-hand should cost 'bonus_actions', got '{off_attack.costs[0].cost_type}'")

    return result1 and result2


def test_off_hand_no_ability_modifier():
    """Test that off-hand attacks don't add ability modifier to damage."""
    print("\n" + "=" * 70)
    print(" TEST 3: Off-hand damage excludes ability modifier")
    print("=" * 70)

    reset_entities()
    attacker = create_goblin(name="Attacker", position=(0, 0))
    target = create_goblin(name="Target", position=(1, 0))

    # Equip light dagger in off-hand
    dagger = create_light_dagger(attacker.uuid)
    attacker.equipment.equip(dagger, WeaponSlot.MELEE_OFF)
    Entity.update_all_entities_senses()

    # Get damages for main hand vs off hand
    main_damages = attacker.get_damages(WeaponSlot.MELEE_MAIN, target.uuid)
    off_damages = attacker.get_damages(WeaponSlot.MELEE_OFF, target.uuid)

    main_bonus = main_damages[0].damage_bonus.normalized_score
    off_bonus = off_damages[0].damage_bonus.normalized_score

    print(f"\nAttacker DEX modifier: {attacker.ability_scores.dexterity.modifier}")
    print(f"Main hand damage bonus: {main_bonus}")
    print(f"Off-hand damage bonus: {off_bonus}")

    # Goblin has +2 DEX which applies to finesse main hand but not off-hand
    result = main_bonus > off_bonus
    if result:
        print(f"[PASS] Main hand bonus ({main_bonus}) > Off-hand bonus ({off_bonus})")
    else:
        print(f"[FAIL] Expected main hand bonus ({main_bonus}) > off-hand bonus ({off_bonus})")

    return result


def test_full_two_weapon_combat():
    """Test a full combat round using two-weapon fighting."""
    print("\n" + "=" * 70)
    print(" TEST 4: Full two-weapon fighting combat round")
    print("=" * 70)

    reset_entities()
    attacker = create_goblin(name="Dual Wielder", position=(0, 0))
    target = create_goblin(name="Target", position=(1, 0))

    # Equip light dagger in off-hand (main hand already has scimitar)
    dagger = create_light_dagger(attacker.uuid)
    attacker.equipment.equip(dagger, WeaponSlot.MELEE_OFF)
    Entity.update_all_entities_senses()

    print(f"\nSetup: {attacker.name} has scimitar (main) and dagger (off)")
    print(f"Action Economy: actions={attacker.action_economy.actions.normalized_score}, "
          f"bonus_actions={attacker.action_economy.bonus_actions.normalized_score}")

    target_hp_start = target.get_hp()
    print(f"Target HP: {target_hp_start}")

    # Main hand attack (costs action)
    print("\n--- Main Hand Attack ---")
    main_attack = Attack(
        source_entity_uuid=attacker.uuid,
        target_entity_uuid=target.uuid,
        weapon_slot=WeaponSlot.MELEE_MAIN,
        name="Scimitar attack"
    )
    main_event = main_attack.apply()
    print(f"Result: {main_event.attack_outcome}")
    print(f"Actions remaining: {attacker.action_economy.actions.normalized_score}")

    # Off-hand attack (costs bonus action)
    print("\n--- Off Hand Attack ---")
    off_attack = Attack(
        source_entity_uuid=attacker.uuid,
        target_entity_uuid=target.uuid,
        weapon_slot=WeaponSlot.MELEE_OFF,
        name="Dagger attack"
    )
    off_event = off_attack.apply()
    print(f"Result: {off_event.attack_outcome}")
    print(f"Bonus actions remaining: {attacker.action_economy.bonus_actions.normalized_score}")

    target_hp_end = target.get_hp()
    print(f"\nTarget HP after attacks: {target_hp_end}")

    # Verify action economy was consumed correctly
    actions_ok = attacker.action_economy.actions.normalized_score == 0
    bonus_ok = attacker.action_economy.bonus_actions.normalized_score == 0

    if actions_ok and bonus_ok:
        print("[PASS] Both action and bonus action consumed correctly")
        return True
    else:
        print(f"[FAIL] Actions={attacker.action_economy.actions.normalized_score} (expected 0), "
              f"Bonus={attacker.action_economy.bonus_actions.normalized_score} (expected 0)")
        return False


if __name__ == "__main__":
    result1 = test_light_weapon_requirement()
    result2 = test_off_hand_costs_bonus_action()
    result3 = test_off_hand_no_ability_modifier()
    result4 = test_full_two_weapon_combat()

    print("\n" + "=" * 70)
    print(" SUMMARY")
    print("=" * 70)
    print(f"LIGHT weapon requirement:     {'PASS' if result1 else 'FAIL'}")
    print(f"Off-hand costs bonus action:  {'PASS' if result2 else 'FAIL'}")
    print(f"Off-hand no ability modifier: {'PASS' if result3 else 'FAIL'}")
    print(f"Full combat round:            {'PASS' if result4 else 'FAIL'}")

    if all([result1, result2, result3, result4]):
        print("\nALL TESTS PASSED!")
    else:
        print("\nSOME TESTS FAILED!")
