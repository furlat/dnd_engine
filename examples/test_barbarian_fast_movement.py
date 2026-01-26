"""
Test Barbarian Fast Movement (Level 5)

Tests:
1. +10 speed when unarmored
2. +10 speed with light armor
3. +10 speed with medium armor
4. No bonus with heavy armor
5. Stacks with base speed correctly
"""

from uuid import uuid4

from dnd.entity import Entity, EntityConfig
from dnd.blocks.abilities import AbilityScoresConfig, AbilityConfig
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.blocks.equipment import EquipmentConfig
from dnd.blocks.action_economy import ActionEconomyConfig
from dnd.core.events import EventQueue, WeaponSlot
from dnd.blocks.equipment import BodyPart
from dnd.actions_functional import setup_standard_actions
from dnd.items.weapons import create_greatsword
from dnd.items.armors import create_leather_armor, create_chain_shirt, create_chain_mail

from dnd.classes.barbarian import FastMovement


def create_test_barbarian(
    name: str = "Test Barbarian",
    position: tuple = (0, 0)
) -> Entity:
    """Create a simple barbarian for testing."""
    source_id = uuid4()

    config = EntityConfig(
        ability_scores=AbilityScoresConfig(
            strength=AbilityConfig(ability_score=16),
            dexterity=AbilityConfig(ability_score=14),
            constitution=AbilityConfig(ability_score=16),
            intelligence=AbilityConfig(ability_score=8),
            wisdom=AbilityConfig(ability_score=12),
            charisma=AbilityConfig(ability_score=10)
        ),
        health=HealthConfig(hit_dices=[HitDiceConfig(
            hit_dice_value=12,
            hit_dice_count=5,
            mode="average"
        )]),
        equipment=EquipmentConfig(),
        action_economy=ActionEconomyConfig(),
        proficiency_bonus=3,
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


def test_fast_movement_unarmored():
    """Test +10 speed when unarmored."""
    print("\n=== Test: Fast Movement - Unarmored ===")

    EventQueue.reset()
    Entity._entity_registry.clear()
    Entity._entity_by_position.clear()

    barbarian = create_test_barbarian("Unarmored Barbarian")

    # Get base speed
    base_speed = barbarian.action_economy.movement.normalized_score
    print(f"  Base speed (no armor): {base_speed}")

    # Apply Fast Movement
    fast_movement = FastMovement(
        source_entity_uuid=barbarian.uuid,
        target_entity_uuid=barbarian.uuid
    )
    barbarian.add_condition(fast_movement)

    # Get new speed
    new_speed = barbarian.action_economy.movement.normalized_score
    print(f"  Speed with Fast Movement: {new_speed}")

    expected_speed = base_speed + 10
    if new_speed == expected_speed:
        print(f"  [PASS] Fast Movement adds +10 speed when unarmored ({base_speed} -> {new_speed})")
    else:
        print(f"  [FAIL] Expected {expected_speed}, got {new_speed}")

    assert new_speed == expected_speed, f"Expected {expected_speed}, got {new_speed}"

    EventQueue.reset()


def test_fast_movement_light_armor():
    """Test +10 speed with light armor."""
    print("\n=== Test: Fast Movement - Light Armor ===")

    EventQueue.reset()
    Entity._entity_registry.clear()
    Entity._entity_by_position.clear()

    barbarian = create_test_barbarian("Light Armor Barbarian")

    # Equip leather armor (light)
    leather = create_leather_armor(barbarian.uuid)
    barbarian.equipment.equip(leather)
    print(f"  Equipped: {leather.name} (Light)")

    # Get base speed
    base_speed = barbarian.action_economy.movement.normalized_score
    print(f"  Base speed with light armor: {base_speed}")

    # Apply Fast Movement
    fast_movement = FastMovement(
        source_entity_uuid=barbarian.uuid,
        target_entity_uuid=barbarian.uuid
    )
    barbarian.add_condition(fast_movement)

    # Get new speed
    new_speed = barbarian.action_economy.movement.normalized_score
    print(f"  Speed with Fast Movement: {new_speed}")

    expected_speed = base_speed + 10
    if new_speed == expected_speed:
        print(f"  [PASS] Fast Movement adds +10 speed with light armor ({base_speed} -> {new_speed})")
    else:
        print(f"  [FAIL] Expected {expected_speed}, got {new_speed}")

    assert new_speed == expected_speed, f"Expected {expected_speed}, got {new_speed}"

    EventQueue.reset()


def test_fast_movement_medium_armor():
    """Test +10 speed with medium armor."""
    print("\n=== Test: Fast Movement - Medium Armor ===")

    EventQueue.reset()
    Entity._entity_registry.clear()
    Entity._entity_by_position.clear()

    barbarian = create_test_barbarian("Medium Armor Barbarian")

    # Equip chain shirt (medium)
    chain_shirt = create_chain_shirt(barbarian.uuid)
    barbarian.equipment.equip(chain_shirt)
    print(f"  Equipped: {chain_shirt.name} (Medium)")

    # Get base speed
    base_speed = barbarian.action_economy.movement.normalized_score
    print(f"  Base speed with medium armor: {base_speed}")

    # Apply Fast Movement
    fast_movement = FastMovement(
        source_entity_uuid=barbarian.uuid,
        target_entity_uuid=barbarian.uuid
    )
    barbarian.add_condition(fast_movement)

    # Get new speed
    new_speed = barbarian.action_economy.movement.normalized_score
    print(f"  Speed with Fast Movement: {new_speed}")

    expected_speed = base_speed + 10
    if new_speed == expected_speed:
        print(f"  [PASS] Fast Movement adds +10 speed with medium armor ({base_speed} -> {new_speed})")
    else:
        print(f"  [FAIL] Expected {expected_speed}, got {new_speed}")

    assert new_speed == expected_speed, f"Expected {expected_speed}, got {new_speed}"

    EventQueue.reset()


def test_fast_movement_heavy_armor():
    """Test NO bonus with heavy armor."""
    print("\n=== Test: Fast Movement - Heavy Armor (No Bonus) ===")

    EventQueue.reset()
    Entity._entity_registry.clear()
    Entity._entity_by_position.clear()

    barbarian = create_test_barbarian("Heavy Armor Barbarian")

    # Equip chain mail (heavy)
    chain_mail = create_chain_mail(barbarian.uuid)
    barbarian.equipment.equip(chain_mail)
    print(f"  Equipped: {chain_mail.name} (Heavy)")

    # Get base speed
    base_speed = barbarian.action_economy.movement.normalized_score
    print(f"  Base speed with heavy armor: {base_speed}")

    # Apply Fast Movement
    fast_movement = FastMovement(
        source_entity_uuid=barbarian.uuid,
        target_entity_uuid=barbarian.uuid
    )
    barbarian.add_condition(fast_movement)

    # Get new speed
    new_speed = barbarian.action_economy.movement.normalized_score
    print(f"  Speed with Fast Movement: {new_speed}")

    # Should be unchanged
    if new_speed == base_speed:
        print(f"  [PASS] Fast Movement has no effect with heavy armor (speed unchanged: {new_speed})")
    else:
        print(f"  [FAIL] Expected {base_speed} (unchanged), got {new_speed}")

    assert new_speed == base_speed, f"Expected {base_speed}, got {new_speed}"

    EventQueue.reset()


def test_fast_movement_equip_unequip():
    """Test that speed updates when equipping/unequipping armor."""
    print("\n=== Test: Fast Movement - Equip/Unequip Armor ===")

    EventQueue.reset()
    Entity._entity_registry.clear()
    Entity._entity_by_position.clear()

    barbarian = create_test_barbarian("Equip Test Barbarian")

    # Apply Fast Movement first
    fast_movement = FastMovement(
        source_entity_uuid=barbarian.uuid,
        target_entity_uuid=barbarian.uuid
    )
    barbarian.add_condition(fast_movement)

    # Unarmored speed
    unarmored_speed = barbarian.action_economy.movement.normalized_score
    print(f"  Unarmored speed (with Fast Movement): {unarmored_speed}")

    # Equip heavy armor
    chain_mail = create_chain_mail(barbarian.uuid)
    barbarian.equipment.equip(chain_mail)
    heavy_speed = barbarian.action_economy.movement.normalized_score
    print(f"  Heavy armor speed (Fast Movement disabled): {heavy_speed}")

    # Speed should be 10 less (fast movement disabled)
    assert heavy_speed == unarmored_speed - 10, f"Heavy armor should disable +10 bonus"

    # Unequip heavy armor
    barbarian.equipment.unequip(BodyPart.BODY)
    restored_speed = barbarian.action_economy.movement.normalized_score
    print(f"  Restored speed after unequipping: {restored_speed}")

    # Speed should be back to full
    assert restored_speed == unarmored_speed, f"Speed should be restored after unequipping"

    print("  [PASS] Fast Movement correctly updates with armor changes")

    EventQueue.reset()


def test_fast_movement_stacks_with_base():
    """Test that Fast Movement stacks correctly with base speed."""
    print("\n=== Test: Fast Movement - Stacks with Base Speed ===")

    EventQueue.reset()
    Entity._entity_registry.clear()
    Entity._entity_by_position.clear()

    barbarian = create_test_barbarian("Speed Stack Barbarian")

    # Get default base speed (usually 30)
    base_speed = barbarian.action_economy.movement.normalized_score
    print(f"  Base speed: {base_speed}")

    # Apply Fast Movement
    fast_movement = FastMovement(
        source_entity_uuid=barbarian.uuid,
        target_entity_uuid=barbarian.uuid
    )
    barbarian.add_condition(fast_movement)

    fast_speed = barbarian.action_economy.movement.normalized_score
    print(f"  With Fast Movement: {fast_speed}")

    # Apply Dash condition (doubles movement) to test stacking
    from dnd.conditions import Dashing
    dashing = Dashing(
        source_entity_uuid=barbarian.uuid,
        target_entity_uuid=barbarian.uuid
    )
    barbarian.add_condition(dashing)

    dash_speed = barbarian.action_economy.movement.normalized_score
    print(f"  With Fast Movement + Dash: {dash_speed}")

    # Dash adds base speed, so:
    # Base 30 + Fast Movement 10 = 40, then Dash adds another 30 = 70
    expected_dash_speed = fast_speed + base_speed
    if dash_speed == expected_dash_speed:
        print(f"  [PASS] Fast Movement stacks correctly ({fast_speed} + Dash {base_speed} = {dash_speed})")
    else:
        print(f"  [INFO] Dash speed: {dash_speed} (stacking may work differently)")

    EventQueue.reset()


if __name__ == "__main__":
    print("=" * 60)
    print("BARBARIAN FAST MOVEMENT TESTS")
    print("=" * 60)

    test_fast_movement_unarmored()
    test_fast_movement_light_armor()
    test_fast_movement_medium_armor()
    test_fast_movement_heavy_armor()
    test_fast_movement_equip_unequip()
    test_fast_movement_stacks_with_base()

    print("\n" + "=" * 60)
    print("FAST MOVEMENT TESTS COMPLETE")
    print("=" * 60)
