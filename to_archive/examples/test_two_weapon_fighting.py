"""
Test Two-Weapon Fighting rules:
1. Only LIGHT weapons can be equipped in off-hand slots
2. Off-hand attacks cost a bonus action (not an action)
3. Off-hand attacks don't add ability modifier to damage
4. Two-Weapon Fighting style adds ability modifier to off-hand damage
"""

from dnd.monsters.bestiary import create_goblin
from dnd.blocks.equipment import Weapon, WeaponProperty, WeaponSlot
from dnd.core.modifiers import DamageType
from dnd.core.values import ModifiableValue
from dnd.core.events import RangeType, Range
from dnd.entity import Entity
from dnd.actions import Attack
from dnd.classes.fighter import FightingStyleTwoWeaponFighting
from dnd.utils import reset_combat_state, set_hp
from dnd.core.gridmap import get_map


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

    reset_combat_state()
    get_map().create_rectangle(0, 0, 20, 20)
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

    reset_combat_state()
    get_map().create_rectangle(0, 0, 20, 20)
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

    reset_combat_state()
    get_map().create_rectangle(0, 0, 20, 20)
    attacker = create_goblin(name="Attacker", position=(0, 0))
    target = create_goblin(name="Target", position=(1, 0))

    # Equip light dagger in off-hand
    dagger = create_light_dagger(attacker.uuid)
    attacker.equipment.equip(dagger, WeaponSlot.MELEE_OFF)
    Entity.update_all_entities_senses()

    # Get damages for main hand vs off hand
    main_damages = attacker.get_damages(WeaponSlot.MELEE_MAIN, target.uuid)
    off_damages = attacker.get_damages(WeaponSlot.MELEE_OFF, target.uuid)

    assert main_damages[0].damage_bonus is not None, "Main hand damage bonus should exist"
    assert off_damages[0].damage_bonus is not None, "Off-hand damage bonus should exist"
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

    reset_combat_state()
    get_map().create_rectangle(0, 0, 20, 20)
    attacker = create_goblin(name="Dual Wielder", position=(0, 0))
    target = create_goblin(name="Target", position=(1, 0))

    # Equip light dagger in off-hand (main hand already has scimitar)
    dagger = create_light_dagger(attacker.uuid)
    attacker.equipment.equip(dagger, WeaponSlot.MELEE_OFF)
    Entity.update_all_entities_senses()

    # Set target HP high so it can't die from first hit
    set_hp(target, 100)

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
    assert main_event is not None, "Main attack event should not be None"
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
    assert off_event is not None, "Off-hand attack event should not be None"
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


def test_twf_style_adds_ability_modifier():
    """Test that TWF fighting style adds ability modifier to off-hand damage."""
    print("\n" + "=" * 70)
    print(" TEST 5: TWF style adds ability modifier to off-hand")
    print("=" * 70)

    reset_combat_state()
    get_map().create_rectangle(0, 0, 20, 20)
    attacker = create_goblin(name="Attacker", position=(0, 0))
    target = create_goblin(name="Target", position=(1, 0))

    # Equip light dagger in off-hand
    dagger = create_light_dagger(attacker.uuid)
    attacker.equipment.equip(dagger, WeaponSlot.MELEE_OFF)
    Entity.update_all_entities_senses()

    # Get off-hand damage WITHOUT TWF style
    off_damages_before = attacker.get_damages(WeaponSlot.MELEE_OFF, target.uuid)
    assert off_damages_before[0].damage_bonus is not None, "Damage bonus should exist"
    off_bonus_before = off_damages_before[0].damage_bonus.normalized_score

    print(f"\nAttacker DEX modifier: {attacker.ability_scores.dexterity.modifier}")
    print(f"Off-hand damage bonus WITHOUT TWF: {off_bonus_before}")

    # Apply TWF fighting style
    twf = FightingStyleTwoWeaponFighting(
        source_entity_uuid=attacker.uuid,
        target_entity_uuid=attacker.uuid
    )
    attacker.add_condition(twf)

    # Get off-hand damage WITH TWF style
    off_damages_after = attacker.get_damages(WeaponSlot.MELEE_OFF, target.uuid)
    assert off_damages_after[0].damage_bonus is not None, "Damage bonus should exist"
    off_bonus_after = off_damages_after[0].damage_bonus.normalized_score

    print(f"Off-hand damage bonus WITH TWF: {off_bonus_after}")

    # The difference should be the ability modifier (DEX for finesse weapon)
    dex_mod = attacker.ability_scores.dexterity.modifier
    expected_bonus = off_bonus_before + dex_mod

    result = off_bonus_after == expected_bonus
    if result:
        print(f"[PASS] TWF adds DEX modifier (+{dex_mod}): {off_bonus_before} -> {off_bonus_after}")
    else:
        print(f"[FAIL] Expected {expected_bonus}, got {off_bonus_after}")

    return result


def test_twf_finesse_uses_higher_ability():
    """Test that TWF with finesse weapon uses higher of STR/DEX."""
    print("\n" + "=" * 70)
    print(" TEST 6: TWF finesse uses higher of STR/DEX")
    print("=" * 70)

    reset_combat_state()
    get_map().create_rectangle(0, 0, 20, 20)
    # Create a strong fighter (high STR, low DEX)
    from uuid import uuid4
    from dnd.entity import Entity, EntityConfig
    from dnd.blocks.abilities import AbilityScoresConfig, AbilityConfig
    from dnd.blocks.health import HealthConfig, HitDiceConfig
    from dnd.blocks.action_economy import ActionEconomyConfig

    config = EntityConfig(
        ability_scores=AbilityScoresConfig(
            strength=AbilityConfig(ability_score=18),  # +4 modifier
            dexterity=AbilityConfig(ability_score=10),  # +0 modifier
            constitution=AbilityConfig(ability_score=10),
            intelligence=AbilityConfig(ability_score=10),
            wisdom=AbilityConfig(ability_score=10),
            charisma=AbilityConfig(ability_score=10)
        ),
        health=HealthConfig(hit_dices=[HitDiceConfig(hit_dice_value=8, hit_dice_count=1)]),
        action_economy=ActionEconomyConfig(movement=30),
        position=(0, 0)
    )
    attacker = Entity.create(source_entity_uuid=uuid4(), name="Strong Fighter", config=config)
    target = create_goblin(name="Target", position=(1, 0))

    # Equip finesse dagger in off-hand (should use STR because STR > DEX)
    dagger = create_light_dagger(attacker.uuid)
    attacker.equipment.equip(dagger, WeaponSlot.MELEE_OFF)
    Entity.update_all_entities_senses()

    print(f"\nAttacker STR modifier: {attacker.ability_scores.strength.modifier}")
    print(f"Attacker DEX modifier: {attacker.ability_scores.dexterity.modifier}")

    # Apply TWF fighting style
    twf = FightingStyleTwoWeaponFighting(
        source_entity_uuid=attacker.uuid,
        target_entity_uuid=attacker.uuid
    )
    attacker.add_condition(twf)

    # Get off-hand damage WITH TWF style
    off_damages = attacker.get_damages(WeaponSlot.MELEE_OFF, target.uuid)
    assert off_damages[0].damage_bonus is not None, "Damage bonus should exist"
    off_bonus = off_damages[0].damage_bonus.normalized_score

    print(f"Off-hand damage bonus WITH TWF: {off_bonus}")

    # Should use STR (+4) because it's higher than DEX (+0)
    str_mod = attacker.ability_scores.strength.modifier
    dex_mod = attacker.ability_scores.dexterity.modifier
    expected_mod = max(str_mod, dex_mod)

    result = off_bonus == expected_mod
    if result:
        print(f"[PASS] TWF uses higher modifier (STR +{str_mod} > DEX +{dex_mod}): bonus = {off_bonus}")
    else:
        print(f"[FAIL] Expected {expected_mod}, got {off_bonus}")

    return result


def test_twf_main_hand_unaffected():
    """Test that main-hand damage is unaffected by TWF style."""
    print("\n" + "=" * 70)
    print(" TEST 7: Main-hand unaffected by TWF style")
    print("=" * 70)

    reset_combat_state()
    get_map().create_rectangle(0, 0, 20, 20)
    attacker = create_goblin(name="Attacker", position=(0, 0))
    target = create_goblin(name="Target", position=(1, 0))

    # Equip light dagger in off-hand
    dagger = create_light_dagger(attacker.uuid)
    attacker.equipment.equip(dagger, WeaponSlot.MELEE_OFF)
    Entity.update_all_entities_senses()

    # Get main-hand damage BEFORE TWF style
    main_damages_before = attacker.get_damages(WeaponSlot.MELEE_MAIN, target.uuid)
    assert main_damages_before[0].damage_bonus is not None, "Damage bonus should exist"
    main_bonus_before = main_damages_before[0].damage_bonus.normalized_score

    print(f"\nMain-hand damage bonus BEFORE TWF: {main_bonus_before}")

    # Apply TWF fighting style
    twf = FightingStyleTwoWeaponFighting(
        source_entity_uuid=attacker.uuid,
        target_entity_uuid=attacker.uuid
    )
    attacker.add_condition(twf)

    # Get main-hand damage AFTER TWF style
    main_damages_after = attacker.get_damages(WeaponSlot.MELEE_MAIN, target.uuid)
    assert main_damages_after[0].damage_bonus is not None, "Damage bonus should exist"
    main_bonus_after = main_damages_after[0].damage_bonus.normalized_score

    print(f"Main-hand damage bonus AFTER TWF: {main_bonus_after}")

    result = main_bonus_before == main_bonus_after
    if result:
        print(f"[PASS] Main-hand bonus unchanged: {main_bonus_before} -> {main_bonus_after}")
    else:
        print(f"[FAIL] Main-hand bonus changed: {main_bonus_before} -> {main_bonus_after}")

    return result


def test_twf_condition_removal():
    """Test that removing TWF style reverts off-hand damage."""
    print("\n" + "=" * 70)
    print(" TEST 8: TWF condition removal reverts off-hand damage")
    print("=" * 70)

    reset_combat_state()
    get_map().create_rectangle(0, 0, 20, 20)
    attacker = create_goblin(name="Attacker", position=(0, 0))
    target = create_goblin(name="Target", position=(1, 0))

    # Equip light dagger in off-hand
    dagger = create_light_dagger(attacker.uuid)
    attacker.equipment.equip(dagger, WeaponSlot.MELEE_OFF)
    Entity.update_all_entities_senses()

    # Get off-hand damage WITHOUT TWF style
    off_damages_before = attacker.get_damages(WeaponSlot.MELEE_OFF, target.uuid)
    assert off_damages_before[0].damage_bonus is not None, "Damage bonus should exist"
    off_bonus_before = off_damages_before[0].damage_bonus.normalized_score

    print(f"\nOff-hand damage bonus WITHOUT TWF: {off_bonus_before}")

    # Apply TWF fighting style
    twf = FightingStyleTwoWeaponFighting(
        source_entity_uuid=attacker.uuid,
        target_entity_uuid=attacker.uuid
    )
    attacker.add_condition(twf)

    # Verify TWF is active
    off_damages_with = attacker.get_damages(WeaponSlot.MELEE_OFF, target.uuid)
    assert off_damages_with[0].damage_bonus is not None, "Damage bonus should exist"
    off_bonus_with = off_damages_with[0].damage_bonus.normalized_score
    print(f"Off-hand damage bonus WITH TWF: {off_bonus_with}")

    # Remove TWF style
    attacker.remove_condition("Fighting Style: Two-Weapon Fighting")

    # Get off-hand damage AFTER removal
    off_damages_after = attacker.get_damages(WeaponSlot.MELEE_OFF, target.uuid)
    assert off_damages_after[0].damage_bonus is not None, "Damage bonus should exist"
    off_bonus_after = off_damages_after[0].damage_bonus.normalized_score

    print(f"Off-hand damage bonus AFTER removal: {off_bonus_after}")

    result = off_bonus_after == off_bonus_before
    if result:
        print(f"[PASS] Off-hand bonus reverted: {off_bonus_before} -> {off_bonus_with} -> {off_bonus_after}")
    else:
        print(f"[FAIL] Off-hand bonus not reverted: expected {off_bonus_before}, got {off_bonus_after}")

    return result


if __name__ == "__main__":
    result1 = test_light_weapon_requirement()
    result2 = test_off_hand_costs_bonus_action()
    result3 = test_off_hand_no_ability_modifier()
    result4 = test_full_two_weapon_combat()
    result5 = test_twf_style_adds_ability_modifier()
    result6 = test_twf_finesse_uses_higher_ability()
    result7 = test_twf_main_hand_unaffected()
    result8 = test_twf_condition_removal()

    print("\n" + "=" * 70)
    print(" SUMMARY")
    print("=" * 70)
    print(f"LIGHT weapon requirement:      {'PASS' if result1 else 'FAIL'}")
    print(f"Off-hand costs bonus action:   {'PASS' if result2 else 'FAIL'}")
    print(f"Off-hand no ability modifier:  {'PASS' if result3 else 'FAIL'}")
    print(f"Full combat round:             {'PASS' if result4 else 'FAIL'}")
    print(f"TWF adds ability modifier:     {'PASS' if result5 else 'FAIL'}")
    print(f"TWF finesse uses higher:       {'PASS' if result6 else 'FAIL'}")
    print(f"Main-hand unaffected:          {'PASS' if result7 else 'FAIL'}")
    print(f"TWF removal reverts:           {'PASS' if result8 else 'FAIL'}")

    if all([result1, result2, result3, result4, result5, result6, result7, result8]):
        print("\nALL TESTS PASSED!")
    else:
        print("\nSOME TESTS FAILED!")
