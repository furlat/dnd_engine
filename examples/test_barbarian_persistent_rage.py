"""
Test Barbarian Persistent Rage (Level 15)

Tests:
1. Rage doesn't end from inactivity (no attack/damage)
2. Confirms rage_maintenance_processor checks for PersistentRage
3. Still ends if unconscious (future - needs unconscious system)
"""

from uuid import uuid4

from dnd.entity import Entity, EntityConfig
from dnd.blocks.abilities import AbilityScoresConfig, AbilityConfig
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.blocks.equipment import EquipmentConfig
from dnd.blocks.action_economy import ActionEconomyConfig
from dnd.core.events import WeaponSlot
from dnd.core.gridmap import get_map
from dnd.utils import reset_combat_state
from dnd.actions_functional import setup_standard_actions
from dnd.items.weapons import create_greatsword

from dnd.classes.rage import Raging
from dnd.classes.barbarian import PersistentRage


def create_test_barbarian(
    name: str = "Test Barbarian",
    position: tuple = (0, 0)
) -> Entity:
    """Create a simple barbarian for testing."""
    source_id = uuid4()

    config = EntityConfig(
        ability_scores=AbilityScoresConfig(
            strength=AbilityConfig(ability_score=20),
            dexterity=AbilityConfig(ability_score=14),
            constitution=AbilityConfig(ability_score=18),
            intelligence=AbilityConfig(ability_score=8),
            wisdom=AbilityConfig(ability_score=12),
            charisma=AbilityConfig(ability_score=10)
        ),
        health=HealthConfig(hit_dices=[HitDiceConfig(
            hit_dice_value=12,
            hit_dice_count=15,  # Level 15
            mode="average"
        )]),
        equipment=EquipmentConfig(),
        action_economy=ActionEconomyConfig(),
        proficiency_bonus=5,
        position=position
    )

    entity = Entity.create(
        name=name,
        source_entity_uuid=source_id,
        config=config
    )

    setup_standard_actions(entity)

    greatsword = create_greatsword(entity.uuid)
    entity.equipment.equip(greatsword, WeaponSlot.MELEE_MAIN)

    return entity


def test_persistent_rage_prevents_inactivity_end():
    """Test that rage doesn't end from inactivity with PersistentRage."""
    print("\n=== Test: Persistent Rage Prevents Inactivity End ===")

    reset_combat_state()
    get_map().create_rectangle(0, 0, 20, 20)

    barbarian = create_test_barbarian("Persistent Barbarian")

    # Apply PersistentRage feature
    persistent = PersistentRage(
        source_entity_uuid=barbarian.uuid,
        target_entity_uuid=barbarian.uuid
    )
    barbarian.add_condition(persistent)

    # Apply Raging condition
    raging = Raging(
        source_entity_uuid=barbarian.uuid,
        target_entity_uuid=barbarian.uuid,
        rage_damage=3  # L15 rage damage
    )
    barbarian.add_condition(raging)

    # Verify conditions
    has_persistent = "PersistentRage" in barbarian.active_conditions
    has_raging = "Raging" in barbarian.active_conditions
    has_attacked = "HasAttacked" in barbarian.active_conditions
    has_taken_damage = "HasTakenDamage" in barbarian.active_conditions
    print(f"  PersistentRage: {has_persistent}")
    print(f"  Raging: {has_raging}")
    print(f"  HasAttacked: {has_attacked}, HasTakenDamage: {has_taken_damage}")

    assert has_persistent, "Should have PersistentRage"
    assert has_raging, "Should be raging"
    assert not has_attacked, "Should NOT have HasAttacked (no attack/damage)"
    assert not has_taken_damage, "Should NOT have HasTakenDamage (no attack/damage)"

    # Simulate next turn start (rage check happens at TURN_START before conditions expire)
    print("  Starting next turn (no attack, no damage taken since last turn)...")
    barbarian.on_turn_start()

    # Rage should STILL be active due to PersistentRage
    still_raging = "Raging" in barbarian.active_conditions
    print(f"  Still raging after turn start: {still_raging}")

    if still_raging:
        print("  [PASS] PersistentRage prevents rage from ending due to inactivity")
    else:
        print("  [FAIL] Rage should not end with PersistentRage")




def test_without_persistent_rage_ends_on_inactivity():
    """Test that WITHOUT PersistentRage, rage ends from inactivity."""
    print("\n=== Test: Without PersistentRage, Rage Ends on Inactivity ===")

    reset_combat_state()
    get_map().create_rectangle(0, 0, 20, 20)

    barbarian = create_test_barbarian("Non-Persistent Barbarian")

    # Apply Raging condition WITHOUT PersistentRage
    raging = Raging(
        source_entity_uuid=barbarian.uuid,
        target_entity_uuid=barbarian.uuid,
        rage_damage=3
    )
    barbarian.add_condition(raging)

    # Verify no PersistentRage
    has_persistent = "PersistentRage" in barbarian.active_conditions
    has_raging = "Raging" in barbarian.active_conditions
    print(f"  PersistentRage: {has_persistent}")
    print(f"  Raging: {has_raging}")

    assert not has_persistent, "Should NOT have PersistentRage"
    assert has_raging, "Should be raging"

    # Simulate next turn start (rage check happens at TURN_START before conditions expire)
    print("  Starting next turn (no attack, no damage taken since last turn)...")
    barbarian.on_turn_start()

    # Rage should end
    still_raging = "Raging" in barbarian.active_conditions
    print(f"  Still raging after turn start: {still_raging}")

    if not still_raging:
        print("  [PASS] Without PersistentRage, rage ends from inactivity")
    else:
        print("  [FAIL] Rage should end without PersistentRage")




def test_persistent_rage_multiple_turns():
    """Test that PersistentRage keeps rage active across multiple idle turns."""
    print("\n=== Test: Persistent Rage Across Multiple Turns ===")

    reset_combat_state()
    get_map().create_rectangle(0, 0, 20, 20)

    barbarian = create_test_barbarian("Multi-Turn Barbarian")

    # Apply PersistentRage and Raging
    persistent = PersistentRage(
        source_entity_uuid=barbarian.uuid,
        target_entity_uuid=barbarian.uuid
    )
    barbarian.add_condition(persistent)

    raging = Raging(
        source_entity_uuid=barbarian.uuid,
        target_entity_uuid=barbarian.uuid,
        rage_damage=3
    )
    barbarian.add_condition(raging)

    # Simulate multiple turns of inactivity
    turns = 5
    rage_persisted = True

    for turn in range(1, turns + 1):
        barbarian.on_turn_start()  # Start of turn
        barbarian.on_turn_end()    # End of turn without action

        still_raging = "Raging" in barbarian.active_conditions
        print(f"  Turn {turn}: Still raging = {still_raging}")

        if not still_raging:
            rage_persisted = False
            break

    if rage_persisted:
        print(f"  [PASS] Rage persisted through {turns} idle turns with PersistentRage")
    else:
        print(f"  [FAIL] Rage ended during turn {turn}")




def test_persistent_rage_is_marker_condition():
    """Test that PersistentRage is a marker condition (no modifiers)."""
    print("\n=== Test: PersistentRage Is Marker Condition ===")

    reset_combat_state()
    get_map().create_rectangle(0, 0, 20, 20)

    barbarian = create_test_barbarian("Marker Test")

    # Get baseline stats
    base_speed = barbarian.action_economy.movement.normalized_score
    base_str_save_adv = barbarian.saving_throws.get_saving_throw("strength").bonus.advantage

    # Apply PersistentRage
    persistent = PersistentRage(
        source_entity_uuid=barbarian.uuid,
        target_entity_uuid=barbarian.uuid
    )
    barbarian.add_condition(persistent)

    # Check stats unchanged
    new_speed = barbarian.action_economy.movement.normalized_score
    new_str_save_adv = barbarian.saving_throws.get_saving_throw("strength").bonus.advantage

    print(f"  Speed: {base_speed} -> {new_speed}")
    print(f"  STR save advantage: {base_str_save_adv} -> {new_str_save_adv}")

    if base_speed == new_speed and base_str_save_adv == new_str_save_adv:
        print("  [PASS] PersistentRage is a marker condition (no stat changes)")
    else:
        print("  [FAIL] PersistentRage should not modify any stats")




def test_rage_ends_when_persistent_rage_removed():
    """Test that removing PersistentRage allows rage to end normally."""
    print("\n=== Test: Rage Ends When PersistentRage Removed ===")

    reset_combat_state()
    get_map().create_rectangle(0, 0, 20, 20)

    barbarian = create_test_barbarian("Removal Test")

    # Apply both conditions
    persistent = PersistentRage(
        source_entity_uuid=barbarian.uuid,
        target_entity_uuid=barbarian.uuid
    )
    barbarian.add_condition(persistent)

    raging = Raging(
        source_entity_uuid=barbarian.uuid,
        target_entity_uuid=barbarian.uuid,
        rage_damage=3
    )
    barbarian.add_condition(raging)

    # First turn end + next turn start - rage should persist (has PersistentRage)
    barbarian.on_turn_end()
    barbarian.on_turn_start()  # Rage maintenance check happens here
    still_raging_turn1 = "Raging" in barbarian.active_conditions
    print(f"  After turn 1 (with PersistentRage): Raging = {still_raging_turn1}")
    assert still_raging_turn1, "Rage should persist with PersistentRage"

    # Remove PersistentRage
    barbarian.remove_condition("PersistentRage")
    has_persistent = "PersistentRage" in barbarian.active_conditions
    print(f"  PersistentRage removed: {not has_persistent}")

    # Second turn end + next turn start - rage should now end
    barbarian.on_turn_end()
    barbarian.on_turn_start()  # Rage maintenance check happens here
    still_raging_turn2 = "Raging" in barbarian.active_conditions
    print(f"  After turn 2 (without PersistentRage): Raging = {still_raging_turn2}")

    if not still_raging_turn2:
        print("  [PASS] Rage ends normally after PersistentRage removed")
    else:
        print("  [FAIL] Rage should end without PersistentRage")




if __name__ == "__main__":
    print("=" * 60)
    print("BARBARIAN PERSISTENT RAGE TESTS")
    print("=" * 60)

    test_persistent_rage_prevents_inactivity_end()
    test_without_persistent_rage_ends_on_inactivity()
    test_persistent_rage_multiple_turns()
    test_persistent_rage_is_marker_condition()
    test_rage_ends_when_persistent_rage_removed()

    print("\n" + "=" * 60)
    print("PERSISTENT RAGE TESTS COMPLETE")
    print("=" * 60)
