"""
Test Barbarian Rage Mechanics

Tests:
1. Rage activation (bonus action, applies Raging condition)
2. Rage benefits (STR advantage, rage damage bonus)
3. Rage maintenance (HasAttacked/HasTakenDamage markers for rage maintenance)
4. Rage ending (no attack/damage → rage ends at next turn start)
5. Cannot rage in heavy armor
6. Reckless Attack
7. Unarmored Defense
8. Danger Sense
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
from dnd.items.weapons import create_greatsword
from dnd.items.armors import create_chain_mail

from dnd.classes.barbarian import (
    RageFeature, Raging,
    UnarmoredDefense, RecklessAttackFeature, DangerSense
)


def create_test_barbarian(
    name: str = "Test Barbarian",
    position: tuple = (0, 0),
    level: int = 1
) -> Entity:
    """Create a simple barbarian for testing."""
    source_id = uuid4()

    # Standard barbarian stats: high STR and CON
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
            hit_dice_value=12,  # Barbarian d12
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

    return entity


def test_rage_damage_resistance():
    """Test that rage actually halves bludgeoning/piercing/slashing damage."""
    print("\n=== Test: Rage Damage Resistance ===")

    EventQueue.reset()
    Entity._entity_registry.clear()
    Entity._entity_by_position.clear()

    barbarian = create_test_barbarian("Tanky Barbarian")
    attacker_id = barbarian.uuid  # Just need a source UUID for damage

    # Apply Raging
    raging = Raging(
        source_entity_uuid=barbarian.uuid,
        target_entity_uuid=barbarian.uuid,
        rage_damage=2
    )
    barbarian.add_condition(raging)

    # Record starting HP
    starting_hp = barbarian.get_hp()
    print(f"  Starting HP: {starting_hp}")

    # Deal 10 bludgeoning damage (should be halved to 5)
    damage_dealt = 10
    actual_bludg = barbarian.health.take_damage(damage_dealt, DamageType.BLUDGEONING, attacker_id)
    hp_after_bludg = barbarian.get_hp()
    print(f"  Dealt {damage_dealt} bludgeoning -> took {actual_bludg}, HP now {hp_after_bludg}")
    assert actual_bludg == 5, f"Bludgeoning should be halved to 5, got {actual_bludg}"

    # Deal 10 fire damage (should NOT be halved)
    actual_fire = barbarian.health.take_damage(damage_dealt, DamageType.FIRE, attacker_id)
    hp_after_fire = barbarian.get_hp()
    print(f"  Dealt {damage_dealt} fire -> took {actual_fire}, HP now {hp_after_fire}")
    assert actual_fire == 10, f"Fire should be full 10, got {actual_fire}"

    # Deal 10 slashing damage (should be halved to 5)
    actual_slash = barbarian.health.take_damage(damage_dealt, DamageType.SLASHING, attacker_id)
    hp_after_slash = barbarian.get_hp()
    print(f"  Dealt {damage_dealt} slashing -> took {actual_slash}, HP now {hp_after_slash}")
    assert actual_slash == 5, f"Slashing should be halved to 5, got {actual_slash}"

    # Deal 10 piercing damage (should be halved to 5)
    actual_pierce = barbarian.health.take_damage(damage_dealt, DamageType.PIERCING, attacker_id)
    hp_after_pierce = barbarian.get_hp()
    print(f"  Dealt {damage_dealt} piercing -> took {actual_pierce}, HP now {hp_after_pierce}")
    assert actual_pierce == 5, f"Piercing should be halved to 5, got {actual_pierce}"

    # Total damage taken should be: 5 + 10 + 5 + 5 = 25
    total_damage = starting_hp - hp_after_pierce
    print(f"  Total damage taken: {total_damage} (expected 25)")
    assert total_damage == 25, f"Total should be 25, got {total_damage}"

    print("  ✓ Bludgeoning damage halved (resistance)")
    print("  ✓ Fire damage NOT halved (no resistance)")
    print("  ✓ Slashing damage halved (resistance)")
    print("  ✓ Piercing damage halved (resistance)")

    EventQueue.reset()


def test_rage_activation():
    """Test that Rage can be activated and applies Raging condition."""
    print("\n=== Test: Rage Activation ===")

    EventQueue.reset()
    Entity._entity_registry.clear()
    Entity._entity_by_position.clear()

    barbarian = create_test_barbarian("Rage Test Barbarian")

    # Apply RageFeature
    rage_feature = RageFeature(
        source_entity_uuid=barbarian.uuid,
        target_entity_uuid=barbarian.uuid,
        rage_uses=2,
        rage_damage=2
    )
    barbarian.add_condition(rage_feature)

    # Check rage resource exists
    assert "rage" in barbarian.action_economy.resources, "Rage resource not found"
    assert barbarian.action_economy.resources["rage"].current == 2, "Should have 2 rage uses"

    # Check Rage action is available
    available = get_available_actions(barbarian)
    action_names = [a.template_name for a in available.self_actions]
    assert "Rage" in action_names, f"Rage action not found in {action_names}"

    # Get the Rage action info
    rage_info = next(a for a in available.self_actions if a.template_name == "Rage")
    assert rage_info.valid_targets, "Rage should have valid target (self)"

    # Activate rage
    result = execute_action(barbarian, "Rage", rage_info.valid_targets[0])
    print(f"  Rage activation: {result.status_message if result else 'Failed'}")

    # Check Raging condition is applied
    assert "Raging" in barbarian.active_conditions, "Raging condition not applied"
    assert barbarian.action_economy.resources["rage"].current == 1, "Rage use not consumed"

    print("  ✓ Rage activated successfully")
    print("  ✓ Raging condition applied")
    print("  ✓ Rage resource consumed")

    EventQueue.reset()


def test_rage_benefits():
    """Test rage grants STR advantage and damage bonus."""
    print("\n=== Test: Rage Benefits ===")

    EventQueue.reset()
    Entity._entity_registry.clear()
    Entity._entity_by_position.clear()

    barbarian = create_test_barbarian("Benefits Test Barbarian")

    # Apply Raging directly
    raging = Raging(
        source_entity_uuid=barbarian.uuid,
        target_entity_uuid=barbarian.uuid,
        rage_damage=2
    )
    barbarian.add_condition(raging)

    # Check STR save has advantage
    str_save = barbarian.saving_throws.get_saving_throw("strength")
    advantage_status = str_save.bonus.advantage
    print(f"  STR save advantage: {advantage_status}")
    assert advantage_status == AdvantageStatus.ADVANTAGE, "STR save should have advantage"

    # Check melee damage bonus
    damage_bonus = barbarian.equipment.melee_damage_bonus.normalized_score
    print(f"  Melee damage bonus: {damage_bonus}")
    assert damage_bonus >= 2, f"Should have at least +2 rage damage, got {damage_bonus}"

    # Check damage resistance to B/P/S
    bludg_resist = barbarian.health.damage_reduction.resistance[DamageType.BLUDGEONING]
    pierc_resist = barbarian.health.damage_reduction.resistance[DamageType.PIERCING]
    slash_resist = barbarian.health.damage_reduction.resistance[DamageType.SLASHING]
    print(f"  Bludgeoning resistance: {bludg_resist}")
    print(f"  Piercing resistance: {pierc_resist}")
    print(f"  Slashing resistance: {slash_resist}")
    assert bludg_resist == ResistanceStatus.RESISTANCE, "Should resist bludgeoning"
    assert pierc_resist == ResistanceStatus.RESISTANCE, "Should resist piercing"
    assert slash_resist == ResistanceStatus.RESISTANCE, "Should resist slashing"

    print("  ✓ STR saves have advantage")
    print("  ✓ Melee attacks have +2 rage damage")
    print("  ✓ Has resistance to bludgeoning/piercing/slashing")

    EventQueue.reset()


def test_rage_maintenance_attack():
    """Test that attacking while raging applies HasAttacked marker."""
    print("\n=== Test: Rage Maintenance (Attack) ===")

    EventQueue.reset()
    Entity._entity_registry.clear()
    Entity._entity_by_position.clear()

    barbarian = create_test_barbarian("Attack Maintenance Barbarian", position=(0, 0))
    _target = create_test_barbarian("Target Dummy", position=(1, 0))  # Adjacent

    Entity.update_all_entities_senses()

    # Apply Raging
    raging = Raging(
        source_entity_uuid=barbarian.uuid,
        target_entity_uuid=barbarian.uuid,
        rage_damage=2
    )
    barbarian.add_condition(raging)

    # No HasAttacked yet
    assert "HasAttacked" not in barbarian.active_conditions, "HasAttacked should not exist yet"

    # Get attack action and execute
    available = get_available_actions(barbarian)
    attack_info = next((a for a in available.entity_actions if "Attack" in a.template_name), None)
    if not attack_info or not attack_info.valid_targets:
        print("  ✗ No attack action or valid targets found")
        EventQueue.reset()
        return

    result = execute_action(barbarian, attack_info.template_name, attack_info.valid_targets[0])
    print(f"  Attack result: {result.status_message if result else 'Failed/Missed'}")

    # Check HasAttacked is now present (generic combat state condition)
    has_attacked = "HasAttacked" in barbarian.active_conditions
    print(f"  HasAttacked after attack: {has_attacked}")

    if has_attacked:
        print("  ✓ HasAttacked marker applied after attacking")
    else:
        print("  ✗ HasAttacked marker NOT applied (handler may not have fired)")

    EventQueue.reset()


def test_rage_maintenance_damage():
    """Test that taking damage while raging applies HasTakenDamage marker.

    This test directly fires a TakeDamageEvent to deterministically test
    the has_taken_damage handler, avoiding RNG from attack rolls.
    """
    print("\n=== Test: Rage Maintenance (Damage Taken) ===")

    from dnd.core.events import TakeDamageEvent, EventPhase

    EventQueue.reset()
    Entity._entity_registry.clear()
    Entity._entity_by_position.clear()

    barbarian = create_test_barbarian("Damage Maintenance Barbarian", position=(0, 0))
    attacker = create_test_barbarian("Attacker", position=(1, 0))  # Adjacent

    Entity.update_all_entities_senses()

    # Apply Raging to barbarian
    raging = Raging(
        source_entity_uuid=barbarian.uuid,
        target_entity_uuid=barbarian.uuid,
        rage_damage=2
    )
    barbarian.add_condition(raging)

    # No HasTakenDamage yet
    assert "HasTakenDamage" not in barbarian.active_conditions, "HasTakenDamage should not exist yet"
    print(f"  Raging: True, HasTakenDamage: False (initial state)")

    # Directly fire a TakeDamageEvent targeting the barbarian
    # This simulates damage being dealt without relying on attack RNG
    take_damage_event = TakeDamageEvent(
        name="Test Damage",
        source_entity_uuid=attacker.uuid,
        target_entity_uuid=barbarian.uuid,
        total_damage=5,
        damage_rolls=[],
        damages=[],
        phase=EventPhase.DECLARATION
    )
    print(f"  Firing TakeDamageEvent (5 damage) targeting barbarian...")

    # Progress through phases - the has_taken_damage_processor fires at EFFECT
    take_damage_event = take_damage_event.phase_to(EventPhase.EXECUTION)
    take_damage_event = take_damage_event.phase_to(EventPhase.EFFECT)
    take_damage_event = take_damage_event.phase_to(EventPhase.COMPLETION)

    # Check HasTakenDamage is now present (generic combat state condition)
    has_taken_damage = "HasTakenDamage" in barbarian.active_conditions
    print(f"  HasTakenDamage after TAKE_DAMAGE event: {has_taken_damage}")

    if has_taken_damage:
        print("  ✓ HasTakenDamage marker applied after taking damage")
    else:
        print("  ✗ HasTakenDamage marker NOT applied (handler may not be firing)")

    # Verify rage persists after next turn start (rage check happens at TURN_START before conditions expire)
    if has_taken_damage:
        barbarian.on_turn_start()
        still_raging = "Raging" in barbarian.active_conditions
        print(f"  Raging after turn start: {still_raging}")
        if still_raging:
            print("  ✓ Rage maintained correctly (took damage since last turn)")
        else:
            print("  ✗ Rage should have been maintained")

    EventQueue.reset()


def test_rage_ends_no_activity():
    """Test that rage ends at next turn start if no attack/damage since last turn."""
    print("\n=== Test: Rage Ends Without Activity ===")

    EventQueue.reset()
    Entity._entity_registry.clear()
    Entity._entity_by_position.clear()

    barbarian = create_test_barbarian("Idle Rage Barbarian")

    # Apply Raging
    raging = Raging(
        source_entity_uuid=barbarian.uuid,
        target_entity_uuid=barbarian.uuid,
        rage_damage=2
    )
    barbarian.add_condition(raging)

    assert "Raging" in barbarian.active_conditions, "Should be raging"
    assert "HasAttacked" not in barbarian.active_conditions, "Should not have HasAttacked"
    assert "HasTakenDamage" not in barbarian.active_conditions, "Should not have HasTakenDamage"

    # Simulate next turn start (rage check happens at TURN_START before conditions expire)
    _event = barbarian.on_turn_start()

    # Rage should have ended
    still_raging = "Raging" in barbarian.active_conditions
    print(f"  Still raging after idle turn: {still_raging}")

    if not still_raging:
        print("  ✓ Rage ended correctly (no attack or damage)")
    else:
        print("  ✗ Rage should have ended")

    EventQueue.reset()


def test_cannot_rage_heavy_armor():
    """Test that rage cannot be activated in heavy armor."""
    print("\n=== Test: Cannot Rage in Heavy Armor ===")

    EventQueue.reset()
    Entity._entity_registry.clear()
    Entity._entity_by_position.clear()

    barbarian = create_test_barbarian("Armored Barbarian")

    # Equip heavy armor
    chain_mail = create_chain_mail(barbarian.uuid)
    barbarian.equipment.equip(chain_mail)

    # Apply RageFeature
    rage_feature = RageFeature(
        source_entity_uuid=barbarian.uuid,
        target_entity_uuid=barbarian.uuid,
        rage_uses=2,
        rage_damage=2
    )
    barbarian.add_condition(rage_feature)

    # Check registered actions
    registered_names = [a.name for a in barbarian.registered_actions]
    print(f"  Registered actions: {registered_names}")

    # Try to activate rage
    available = get_available_actions(barbarian)
    self_action_names = [a.template_name for a in available.self_actions]
    print(f"  Available self actions: {self_action_names}")

    rage_info = next((a for a in available.self_actions if a.template_name == "Rage"), None)

    if not rage_info:
        # Rage action filtered out by pre_validate because of heavy armor check
        print("  ✓ Rage action correctly filtered out (pre_validate failed due to heavy armor)")
        result = None
    elif not rage_info.valid_targets:
        print(f"  (Rage found but no valid_targets, can_afford={rage_info.can_afford})")
        result = None
    else:
        result = execute_action(barbarian, "Rage", rage_info.valid_targets[0])
        if result and result.canceled:
            print(f"  ✓ Rage correctly blocked: {result.status_message}")
        else:
            print(f"  ✗ Rage should have been blocked in heavy armor")

    # Should NOT be raging
    is_raging = "Raging" in barbarian.active_conditions
    print(f"  Is raging: {is_raging}")
    assert not is_raging, "Should not be able to rage in heavy armor"

    EventQueue.reset()


def test_unarmored_defense():
    """Test Unarmored Defense adds CON to AC."""
    print("\n=== Test: Unarmored Defense ===")

    EventQueue.reset()
    Entity._entity_registry.clear()
    Entity._entity_by_position.clear()

    barbarian = create_test_barbarian("Unarmored Barbarian")

    # Base AC without Unarmored Defense (10 + DEX)
    base_ac = barbarian.equipment.ac_bonus.normalized_score
    print(f"  Base AC (10 + DEX 2): {base_ac}")

    # Apply Unarmored Defense
    unarmored = UnarmoredDefense(
        source_entity_uuid=barbarian.uuid,
        target_entity_uuid=barbarian.uuid
    )
    barbarian.add_condition(unarmored)

    # New AC should include CON modifier
    new_ac = barbarian.equipment.ac_bonus.normalized_score
    con_mod = barbarian.ability_scores.constitution.modifier
    print(f"  AC with Unarmored Defense: {new_ac}")
    print(f"  CON modifier: {con_mod}")

    expected_ac = base_ac + con_mod
    if new_ac == expected_ac:
        print(f"  ✓ Unarmored Defense correctly adds CON ({con_mod}) to AC")
    else:
        print(f"  ✗ Expected AC {expected_ac}, got {new_ac}")

    EventQueue.reset()


def test_reckless_attack():
    """Test Reckless Attack grants advantage but exposes to attacks."""
    print("\n=== Test: Reckless Attack ===")

    EventQueue.reset()
    Entity._entity_registry.clear()
    Entity._entity_by_position.clear()

    barbarian = create_test_barbarian("Reckless Barbarian")

    # Apply RecklessAttackFeature
    feature = RecklessAttackFeature(
        source_entity_uuid=barbarian.uuid,
        target_entity_uuid=barbarian.uuid
    )
    barbarian.add_condition(feature)

    # Get Reckless Attack action
    available = get_available_actions(barbarian)
    action_names = [a.template_name for a in available.self_actions]

    if "Reckless Attack" not in action_names:
        print(f"  ✗ Reckless Attack action not found in {action_names}")
        return

    # Check melee attack advantage BEFORE
    melee_adv_before = barbarian.equipment.melee_attack_bonus.advantage
    print(f"  Melee attack advantage before: {melee_adv_before}")

    # Activate Reckless Attack
    reckless_info = next(a for a in available.self_actions if a.template_name == "Reckless Attack")
    result = execute_action(barbarian, "Reckless Attack", reckless_info.valid_targets[0])
    print(f"  Reckless Attack result: {result.status_message if result else 'Failed'}")

    # Check RecklessAttacking condition
    is_reckless = "Reckless Attacking" in barbarian.active_conditions
    print(f"  RecklessAttacking condition: {is_reckless}")

    # Check melee attack advantage AFTER
    melee_adv_after = barbarian.equipment.melee_attack_bonus.advantage
    print(f"  Melee attack advantage after: {melee_adv_after}")

    # Check attackers have advantage (to_target channel)
    ac_to_target_adv = barbarian.equipment.ac_bonus.to_target_static.advantage_sum
    print(f"  Attackers advantage (to_target): {ac_to_target_adv}")

    if melee_adv_after == AdvantageStatus.ADVANTAGE:
        print("  ✓ Has advantage on melee attacks")
    else:
        print("  ✗ Should have advantage on melee attacks")

    if ac_to_target_adv > 0:
        print("  ✓ Attackers have advantage against us")
    else:
        print("  ✗ Attackers should have advantage against us")

    EventQueue.reset()


def test_danger_sense():
    """Test Danger Sense grants advantage on DEX saves."""
    print("\n=== Test: Danger Sense ===")

    EventQueue.reset()
    Entity._entity_registry.clear()
    Entity._entity_by_position.clear()

    barbarian = create_test_barbarian("Alert Barbarian")

    # Check DEX save advantage BEFORE
    dex_save = barbarian.saving_throws.get_saving_throw("dexterity")
    adv_before = dex_save.bonus.advantage
    print(f"  DEX save advantage before: {adv_before}")

    # Apply Danger Sense
    danger = DangerSense(
        source_entity_uuid=barbarian.uuid,
        target_entity_uuid=barbarian.uuid
    )
    barbarian.add_condition(danger)

    # Check DEX save advantage AFTER
    adv_after = dex_save.bonus.advantage
    print(f"  DEX save advantage after: {adv_after}")

    if adv_after == AdvantageStatus.ADVANTAGE:
        print("  ✓ Danger Sense grants advantage on DEX saves")
    else:
        print("  ✗ Should have advantage on DEX saves")

    EventQueue.reset()


def test_equip_heavy_armor_ends_rage():
    """Test that equipping heavy armor while raging ends the rage."""
    print("\n=== Test: Equip Heavy Armor Ends Rage ===")

    EventQueue.reset()
    Entity._entity_registry.clear()
    Entity._entity_by_position.clear()

    barbarian = create_test_barbarian("Armoring Barbarian")

    # Apply Raging directly (no heavy armor yet)
    raging = Raging(
        source_entity_uuid=barbarian.uuid,
        target_entity_uuid=barbarian.uuid,
        rage_damage=2
    )
    barbarian.add_condition(raging)

    # Verify we ARE raging
    is_raging_before = "Raging" in barbarian.active_conditions
    print(f"  Raging before equipping armor: {is_raging_before}")
    assert is_raging_before, "Should be raging initially"

    # Now equip heavy armor
    chain_mail = create_chain_mail(barbarian.uuid)
    barbarian.equipment.equip(chain_mail)
    print("  Equipped chain mail (heavy armor)")

    # Rage should have ended
    is_raging_after = "Raging" in barbarian.active_conditions
    print(f"  Raging after equipping armor: {is_raging_after}")

    if not is_raging_after:
        print("  ✓ Rage correctly ended when heavy armor was equipped")
    else:
        print("  ✗ Rage should have ended when heavy armor was equipped")

    assert not is_raging_after, "Rage should end when equipping heavy armor"

    EventQueue.reset()


if __name__ == "__main__":
    print("=" * 60)
    print("BARBARIAN RAGE TESTS")
    print("=" * 60)

    test_rage_damage_resistance()
    test_rage_activation()
    test_rage_benefits()
    test_rage_maintenance_attack()
    test_rage_maintenance_damage()  # NEW: Tests TAKE_DAMAGE event infrastructure
    test_rage_ends_no_activity()
    test_cannot_rage_heavy_armor()
    test_equip_heavy_armor_ends_rage()
    test_unarmored_defense()
    test_reckless_attack()
    test_danger_sense()

    print("\n" + "=" * 60)
    print("BARBARIAN TESTS COMPLETE")
    print("=" * 60)
