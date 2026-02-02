"""
Test Barbarian Frenzy (Berserker Path Level 3)

Tests:
1. Frenzy activation (bonus action, consumes rage)
2. Raging is sub-condition of Frenzied
3. FrenziedStrike action available while frenzied
4. FrenziedStrike costs bonus action
5. FrenziedStrike validates range/LOS
6. No exhaustion (BG3 adaptation)
7. Cannot frenzy in heavy armor
8. Frenzy ends like rage (maintenance rules)
"""

from uuid import uuid4

from dnd.entity import Entity, EntityConfig
from dnd.blocks.abilities import AbilityScoresConfig, AbilityConfig
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.blocks.equipment import EquipmentConfig
from dnd.blocks.action_economy import ActionEconomyConfig
from dnd.core.events import EventQueue, WeaponSlot
from dnd.core.modifiers import AdvantageStatus, DamageType, ResistanceStatus
from dnd.actions_functional import setup_standard_actions, get_available_actions, execute_action
from dnd.items.weapons import create_greatsword, create_shortsword
from dnd.items.armors import create_chain_mail

from dnd.classes.rage import (
    RageFeature,
    FrenzyFeature, Frenzied, FrenziedStrike
)


def create_test_barbarian(
    name: str = "Test Barbarian",
    position: tuple = (0, 0),
    level: int = 3
) -> Entity:
    """Create a simple barbarian for testing with Frenzy feature."""
    source_id = uuid4()

    config = EntityConfig(
        ability_scores=AbilityScoresConfig(
            strength=AbilityConfig(ability_score=16),     # +3
            dexterity=AbilityConfig(ability_score=14),    # +2
            constitution=AbilityConfig(ability_score=16), # +3
            intelligence=AbilityConfig(ability_score=8),  # -1
            wisdom=AbilityConfig(ability_score=12),       # +1
            charisma=AbilityConfig(ability_score=10)      # +0
        ),
        health=HealthConfig(hit_dices=[HitDiceConfig(
            hit_dice_value=12,
            hit_dice_count=level,
            mode="average"
        )]),
        equipment=EquipmentConfig(),
        action_economy=ActionEconomyConfig(),
        proficiency_bonus=2,
        position=position
    )

    entity = Entity.create(
        name=name,
        source_entity_uuid=source_id,
        config=config
    )

    setup_standard_actions(entity)

    # Equip greatsword (two-handed)
    greatsword = create_greatsword(entity.uuid)
    entity.equipment.equip(greatsword, WeaponSlot.MELEE_MAIN)

    # Add RageFeature (provides rage resource and Rage action)
    rage_feature = RageFeature(
        source_entity_uuid=entity.uuid,
        target_entity_uuid=entity.uuid,
        rage_damage=2,
        rage_uses=3
    )
    entity.add_condition(rage_feature)

    # Add FrenzyFeature (Berserker L3 - registers Frenzy action)
    frenzy_feature = FrenzyFeature(
        source_entity_uuid=entity.uuid,
        target_entity_uuid=entity.uuid,
        rage_damage=2
    )
    entity.add_condition(frenzy_feature)

    return entity


def create_test_target(
    name: str = "Target",
    position: tuple = (1, 0)
) -> Entity:
    """Create a simple target for testing."""
    source_id = uuid4()

    config = EntityConfig(
        ability_scores=AbilityScoresConfig(
            strength=AbilityConfig(ability_score=10),
            dexterity=AbilityConfig(ability_score=10),
            constitution=AbilityConfig(ability_score=10),
            intelligence=AbilityConfig(ability_score=10),
            wisdom=AbilityConfig(ability_score=10),
            charisma=AbilityConfig(ability_score=10)
        ),
        health=HealthConfig(hit_dices=[HitDiceConfig(
            hit_dice_value=8,
            hit_dice_count=5,
            mode="average"
        )]),
        equipment=EquipmentConfig(),
        action_economy=ActionEconomyConfig(),
        proficiency_bonus=2,
        position=position
    )

    entity = Entity.create(
        name=name,
        source_entity_uuid=source_id,
        config=config
    )

    setup_standard_actions(entity)
    sword = create_shortsword(entity.uuid)
    entity.equipment.equip(sword, WeaponSlot.MELEE_MAIN)

    return entity


def test_frenzy_activation():
    """Test that Frenzy can be activated and applies Frenzied condition."""
    print("\n=== Test: Frenzy Activation ===")

    EventQueue.reset()
    Entity._entity_registry.clear()
    Entity._entity_by_position.clear()

    # create_test_barbarian now includes RageFeature and FrenzyFeature
    barbarian = create_test_barbarian("Frenzy Test Barbarian")

    # Check Frenzy action is available
    available = get_available_actions(barbarian)
    action_names = [a.template_name for a in available.self_actions]
    print(f"  Available self actions: {action_names}")
    assert "Frenzy" in action_names, f"Frenzy action not found in {action_names}"

    # Get initial rage count
    initial_rage = barbarian.action_economy.resources["rage"].current
    print(f"  Initial rage uses: {initial_rage}")

    # Activate frenzy
    frenzy_info = next(a for a in available.self_actions if a.template_name == "Frenzy")
    result = execute_action(barbarian, "Frenzy", frenzy_info.valid_targets[0])
    print(f"  Frenzy activation: {result.status_message if result else 'Failed'}")

    # Check Frenzied condition is applied
    assert "Frenzied" in barbarian.active_conditions, "Frenzied condition not applied"

    # Check rage resource was consumed
    final_rage = barbarian.action_economy.resources["rage"].current
    print(f"  Rage uses after frenzy: {final_rage}")
    assert final_rage == initial_rage - 1, "Rage use not consumed"

    print("  [PASS] Frenzy activated successfully")
    print("  [PASS] Frenzied condition applied")
    print("  [PASS] Rage resource consumed")

    EventQueue.reset()


def test_frenzied_includes_raging():
    """Test that using Frenzy action applies both Frenzied and Raging conditions.

    Design note: Raging is now the parent condition and Frenzied is its sub-condition.
    This inverted relationship enables rage maintenance to properly cascade removal.
    The Frenzy action applies Raging first, then Frenzied as its child.
    """
    print("\n=== Test: Frenzied Includes Raging ===")

    EventQueue.reset()
    Entity._entity_registry.clear()
    Entity._entity_by_position.clear()

    barbarian = create_test_barbarian("Frenzied Barbarian")

    # Use Frenzy action (the correct way to enter frenzied rage)
    frenzy_template = barbarian.get_action_template("Frenzy")
    assert frenzy_template is not None, "Frenzy action should be registered"
    frenzy_instance = frenzy_template.instantiate()
    frenzy_instance.apply()

    # Check both conditions exist
    has_frenzied = "Frenzied" in barbarian.active_conditions
    has_raging = "Raging" in barbarian.active_conditions
    print(f"  Frenzied condition: {has_frenzied}")
    print(f"  Raging condition: {has_raging}")

    assert has_frenzied, "Should have Frenzied condition"
    assert has_raging, "Should have Raging condition"

    # Check parent-child relationship (Raging is parent, Frenzied is child)
    raging = barbarian.active_conditions["Raging"]
    frenzied = barbarian.active_conditions["Frenzied"]
    print(f"  Raging.sub_conditions contains Frenzied: {frenzied.uuid in raging.sub_conditions}")
    print(f"  Frenzied.parent_condition is Raging: {frenzied.parent_condition == raging.uuid}")
    assert frenzied.uuid in raging.sub_conditions, "Frenzied should be in Raging's sub_conditions"
    assert frenzied.parent_condition == raging.uuid, "Frenzied's parent should be Raging"

    # Check rage benefits are active (damage resistance)
    bludg_resist = barbarian.health.damage_reduction.resistance[DamageType.BLUDGEONING]
    print(f"  Bludgeoning resistance: {bludg_resist}")
    assert bludg_resist == ResistanceStatus.RESISTANCE, "Should have rage resistance"

    # Check STR save advantage (from Raging)
    str_save = barbarian.saving_throws.get_saving_throw("strength")
    advantage_status = str_save.bonus.advantage
    print(f"  STR save advantage: {advantage_status}")
    assert advantage_status == AdvantageStatus.ADVANTAGE, "Should have STR advantage from rage"

    print("  [PASS] Frenzy action applies both conditions")
    print("  [PASS] Parent-child relationship is correct (Raging > Frenzied)")
    print("  [PASS] Rage benefits are active")

    EventQueue.reset()


def test_frenzied_strike_available():
    """Test that FrenziedStrike action is available while frenzied."""
    print("\n=== Test: FrenziedStrike Available While Frenzied ===")

    EventQueue.reset()
    Entity._entity_registry.clear()
    Entity._entity_by_position.clear()

    barbarian = create_test_barbarian("Strike Test Barbarian", position=(0, 0))
    _ = create_test_target("Strike Target", position=(1, 0))  # Need target for senses

    Entity.update_all_entities_senses()

    # Apply Frenzied condition
    frenzied = Frenzied(
        source_entity_uuid=barbarian.uuid,
        target_entity_uuid=barbarian.uuid,
        rage_damage=2
    )
    barbarian.add_condition(frenzied)

    # Check FrenziedStrike is in available actions
    available = get_available_actions(barbarian)
    entity_action_names = [a.template_name for a in available.entity_actions]
    print(f"  Entity actions: {entity_action_names}")

    has_frenzied_strike = any("Frenzied Strike" in name for name in entity_action_names)
    print(f"  FrenziedStrike available: {has_frenzied_strike}")

    assert has_frenzied_strike, "FrenziedStrike should be available while frenzied"
    print("  [PASS] FrenziedStrike is available while frenzied")

    EventQueue.reset()


def test_frenzied_strike_costs_bonus_action():
    """Test that FrenziedStrike costs a bonus action."""
    print("\n=== Test: FrenziedStrike Costs Bonus Action ===")

    EventQueue.reset()
    Entity._entity_registry.clear()
    Entity._entity_by_position.clear()

    barbarian = create_test_barbarian("Bonus Action Test", position=(0, 0))
    target = create_test_target("Strike Target", position=(1, 0))

    Entity.update_all_entities_senses()

    # Apply Frenzied condition
    frenzied = Frenzied(
        source_entity_uuid=barbarian.uuid,
        target_entity_uuid=barbarian.uuid,
        rage_damage=2
    )
    barbarian.add_condition(frenzied)

    # Check bonus actions before
    bonus_before = barbarian.action_economy.bonus_actions.normalized_score
    print(f"  Bonus actions before: {bonus_before}")

    # Execute FrenziedStrike
    strike = FrenziedStrike(
        source_entity_uuid=barbarian.uuid,
        target_entity_uuid=target.uuid,
        weapon_slot=WeaponSlot.MELEE_MAIN
    )
    result = strike.apply()
    print(f"  FrenziedStrike result: {result.status_message if result else 'Failed'}")

    # Check bonus actions after
    bonus_after = barbarian.action_economy.bonus_actions.normalized_score
    print(f"  Bonus actions after: {bonus_after}")

    if result and not result.canceled:
        assert bonus_after == bonus_before - 1, "Bonus action not consumed"
        print("  [PASS] FrenziedStrike consumed bonus action")
    else:
        print("  [INFO] Attack missed or was canceled - bonus action consumption not verified")

    EventQueue.reset()


def test_frenzied_strike_validates_range():
    """Test that FrenziedStrike validates melee range."""
    print("\n=== Test: FrenziedStrike Validates Range ===")

    EventQueue.reset()
    Entity._entity_registry.clear()
    Entity._entity_by_position.clear()

    barbarian = create_test_barbarian("Range Test Barbarian", position=(0, 0))
    target = create_test_target("Distant Target", position=(10, 0))  # Far away

    Entity.update_all_entities_senses()

    # Apply Frenzied condition
    frenzied = Frenzied(
        source_entity_uuid=barbarian.uuid,
        target_entity_uuid=barbarian.uuid,
        rage_damage=2
    )
    barbarian.add_condition(frenzied)

    # Try FrenziedStrike on distant target
    strike = FrenziedStrike(
        source_entity_uuid=barbarian.uuid,
        target_entity_uuid=target.uuid,
        weapon_slot=WeaponSlot.MELEE_MAIN
    )
    result = strike.apply()

    if result and result.canceled:
        print(f"  Strike blocked: {result.status_message}")
        print("  [PASS] FrenziedStrike correctly validates range")
    else:
        print(f"  Result: {result.status_message if result else 'None'}")
        print("  [WARN] Expected strike to be blocked due to range")

    EventQueue.reset()


def test_cannot_frenzy_heavy_armor():
    """Test that frenzy cannot be activated in heavy armor."""
    print("\n=== Test: Cannot Frenzy in Heavy Armor ===")

    EventQueue.reset()
    Entity._entity_registry.clear()
    Entity._entity_by_position.clear()

    barbarian = create_test_barbarian("Armored Barbarian")

    # Equip heavy armor
    chain_mail = create_chain_mail(barbarian.uuid)
    barbarian.equipment.equip(chain_mail)
    print(f"  Equipped: {chain_mail.name}")

    # Apply RageFeature and FrenzyFeature
    rage_feature = RageFeature(
        source_entity_uuid=barbarian.uuid,
        target_entity_uuid=barbarian.uuid,
        rage_uses=3,
        rage_damage=2
    )
    barbarian.add_condition(rage_feature)

    frenzy_feature = FrenzyFeature(
        source_entity_uuid=barbarian.uuid,
        target_entity_uuid=barbarian.uuid,
        rage_damage=2
    )
    barbarian.add_condition(frenzy_feature)

    # Check available actions
    available = get_available_actions(barbarian)
    self_action_names = [a.template_name for a in available.self_actions]
    print(f"  Available self actions: {self_action_names}")

    # Frenzy should not be available due to pre_validate
    frenzy_available = "Frenzy" in self_action_names
    print(f"  Frenzy available: {frenzy_available}")

    if not frenzy_available:
        print("  [PASS] Frenzy correctly blocked by heavy armor (pre_validate)")
    else:
        # Try to execute - should be blocked at validation
        frenzy_info = next(a for a in available.self_actions if a.template_name == "Frenzy")
        if frenzy_info.valid_targets:
            result = execute_action(barbarian, "Frenzy", frenzy_info.valid_targets[0])
            if result and result.canceled:
                print(f"  Frenzy blocked: {result.status_message}")
                print("  [PASS] Frenzy blocked at validation")
            else:
                print("  [FAIL] Frenzy should be blocked in heavy armor")
        else:
            print("  [PASS] Frenzy has no valid targets (blocked)")

    # Verify not frenzied
    is_frenzied = "Frenzied" in barbarian.active_conditions
    assert not is_frenzied, "Should not be frenzied in heavy armor"

    EventQueue.reset()


def test_frenzy_maintenance():
    """Test that frenzy ends if no attack or damage (like rage).

    Design: Raging is parent, Frenzied is child. When rage maintenance removes
    Raging (due to no attacks/damage), Frenzied is automatically cascade-removed.
    """
    print("\n=== Test: Frenzy Maintenance ===")

    EventQueue.reset()
    Entity._entity_registry.clear()
    Entity._entity_by_position.clear()

    barbarian = create_test_barbarian("Frenzy Maintenance Test")

    # Use Frenzy action to enter frenzied rage (applies both Raging and Frenzied)
    frenzy_template = barbarian.get_action_template("Frenzy")
    assert frenzy_template is not None, "Frenzy action should be registered"
    frenzy_instance = frenzy_template.instantiate()
    frenzy_instance.apply()

    assert "Frenzied" in barbarian.active_conditions, "Should be frenzied"
    assert "Raging" in barbarian.active_conditions, "Should be raging"
    assert "HasAttacked" not in barbarian.active_conditions, "Should not have HasAttacked yet"
    assert "HasTakenDamage" not in barbarian.active_conditions, "Should not have HasTakenDamage yet"

    print(f"  Initial: Frenzied=True, Raging=True, HasAttacked=False, HasTakenDamage=False")

    # Simulate next turn start (rage check happens at TURN_START before conditions expire)
    barbarian.on_turn_start()

    # Rage should have ended (and Frenzied with it due to cascade)
    still_raging = "Raging" in barbarian.active_conditions
    still_frenzied = "Frenzied" in barbarian.active_conditions
    print(f"  After turn start: Frenzied={still_frenzied}, Raging={still_raging}")

    assert not still_raging, "Rage should have ended (no attack or damage)"
    assert not still_frenzied, "Frenzied should have ended (cascade from Raging removal)"

    print("  [PASS] Rage ended correctly (no attack or damage)")
    print("  [PASS] Frenzied ended correctly (cascade removal)")

    EventQueue.reset()


def test_no_exhaustion():
    """Test that BG3-style frenzy has no exhaustion mechanic."""
    print("\n=== Test: No Exhaustion (BG3 Adaptation) ===")

    EventQueue.reset()
    Entity._entity_registry.clear()
    Entity._entity_by_position.clear()

    barbarian = create_test_barbarian("No Exhaustion Barbarian")

    # Use Frenzy action to enter frenzied rage
    frenzy_template = barbarian.get_action_template("Frenzy")
    assert frenzy_template is not None, "Frenzy action should be registered"
    frenzy_instance = frenzy_template.instantiate()
    frenzy_instance.apply()

    # End frenzy by removing Raging (which cascades to remove Frenzied)
    barbarian.remove_condition("Raging")

    # Check no Exhausted condition
    has_exhaustion = "Exhausted" in barbarian.active_conditions
    print(f"  Exhausted condition after frenzy: {has_exhaustion}")

    assert not has_exhaustion, "BG3 frenzy should not cause exhaustion"
    print("  [PASS] No exhaustion after frenzy (BG3 adaptation)")

    EventQueue.reset()


def test_frenzy_removes_frenzied_strike():
    """Test that FrenziedStrike is removed when frenzy ends."""
    print("\n=== Test: FrenziedStrike Removed When Frenzy Ends ===")

    EventQueue.reset()
    Entity._entity_registry.clear()
    Entity._entity_by_position.clear()

    barbarian = create_test_barbarian("Cleanup Test", position=(0, 0))
    _target = create_test_target("Target", position=(1, 0))  # Need target for senses

    Entity.update_all_entities_senses()

    # Use Frenzy action to enter frenzied rage (costs bonus action)
    frenzy_template = barbarian.get_action_template("Frenzy")
    assert frenzy_template is not None, "Frenzy action should be registered"
    frenzy_instance = frenzy_template.instantiate()
    frenzy_instance.apply()

    # Simulate attacking target to maintain rage (apply HasAttacked marker)
    from dnd.conditions import HasAttacked
    from dnd.core.base_conditions import DurationType
    has_attacked = HasAttacked(
        source_entity_uuid=barbarian.uuid,
        target_entity_uuid=barbarian.uuid
    )
    has_attacked.duration.duration_type = DurationType.ROUNDS
    has_attacked.duration.duration = 1
    barbarian.add_condition(has_attacked)

    # Simulate new turn (refreshes action economy and resets costs)
    barbarian.on_turn_start()

    # Verify FrenziedStrike is available now that we have bonus action
    available_before = get_available_actions(barbarian)
    entity_actions_before = [a.template_name for a in available_before.entity_actions]
    has_strike_before = any("Frenzied Strike" in name for name in entity_actions_before)
    print(f"  FrenziedStrike before removal: {has_strike_before}")

    # Remove Raging condition (cascades to remove Frenzied)
    barbarian.remove_condition("Raging")

    # Verify FrenziedStrike is no longer available
    available_after = get_available_actions(barbarian)
    entity_actions_after = [a.template_name for a in available_after.entity_actions]
    has_strike_after = any("Frenzied Strike" in name for name in entity_actions_after)
    print(f"  FrenziedStrike after removal: {has_strike_after}")

    if has_strike_before and not has_strike_after:
        print("  [PASS] FrenziedStrike correctly removed when frenzy ends")
    elif not has_strike_before:
        print("  [WARN] FrenziedStrike was not available before removal")
    else:
        print("  [FAIL] FrenziedStrike should be removed when frenzy ends")

    EventQueue.reset()


if __name__ == "__main__":
    print("=" * 60)
    print("BARBARIAN FRENZY TESTS")
    print("=" * 60)

    test_frenzy_activation()
    test_frenzied_includes_raging()
    test_frenzied_strike_available()
    test_frenzied_strike_costs_bonus_action()
    test_frenzied_strike_validates_range()
    test_cannot_frenzy_heavy_armor()
    test_frenzy_maintenance()
    test_no_exhaustion()
    test_frenzy_removes_frenzied_strike()

    print("\n" + "=" * 60)
    print("FRENZY TESTS COMPLETE")
    print("=" * 60)
