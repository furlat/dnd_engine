"""
Test Survivor (Champion Level 18 Feature)

Tests the turn-start healing when HP <= 50% max.
"""

import sys
sys.path.insert(0, '.')

from uuid import uuid4
from dnd.entity import Entity, EntityConfig
from dnd.blocks.abilities import AbilityScoresConfig, AbilityConfig
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.classes.fighter import Survivor
from dnd.core.base_object import BaseObject
from dnd.core.events import EventQueue
from dnd.core.gridmap import reset_map, get_map


def reset_state():
    """Reset all registries for clean test state."""
    BaseObject._registry.clear()
    Entity._entity_registry.clear()
    Entity._entity_by_position.clear()
    EventQueue.reset()
    reset_map()


def create_fighter(name: str, con_score: int = 14, position: tuple = (0, 0)) -> Entity:
    """Create a fighter with configurable CON for testing."""
    config = EntityConfig(
        ability_scores=AbilityScoresConfig(
            strength=AbilityConfig(ability_score=16),
            dexterity=AbilityConfig(ability_score=14),
            constitution=AbilityConfig(ability_score=con_score),  # CON 14 = +2 mod
            intelligence=AbilityConfig(ability_score=10),
            wisdom=AbilityConfig(ability_score=12),
            charisma=AbilityConfig(ability_score=10)
        ),
        health=HealthConfig(
            hit_dices=[HitDiceConfig(hit_dice_value=10, hit_dice_count=18, mode="average")],  # Champion Level 18: 18d10 average = 99 + CON*18 = 99+36 = 135 HP with CON 14
        ),
        position=position
    )
    entity = Entity.create(source_entity_uuid=uuid4(), name=name, config=config)
    return entity


def test_survivor_heals_at_half_hp():
    """Test Survivor heals when HP <= 50%."""
    print("TEST: Survivor heals at turn start when HP <= 50%")
    reset_state()
    get_map().create_rectangle(0, 0, 5, 5)

    fighter = create_fighter("Champion", con_score=14)  # CON +2
    max_hp = fighter.get_hp()
    print(f"  Max HP: {max_hp}")

    # Apply Survivor condition
    survivor = Survivor(
        source_entity_uuid=fighter.uuid,
        target_entity_uuid=fighter.uuid
    )
    fighter.add_condition(survivor)
    print(f"  Applied Survivor condition")

    # Damage to exactly 50%
    damage_to_half = max_hp // 2
    fighter.health.damage_taken = damage_to_half
    hp_before = fighter.get_hp()
    print(f"  Damaged to {hp_before} HP (50% of {max_hp})")

    # Trigger turn start
    event = fighter.on_turn_start()

    hp_after = fighter.get_hp()
    con_mod = fighter.ability_scores.constitution.modifier
    expected_healing = 5 + con_mod  # 5 + 2 = 7

    print(f"  After turn start: {hp_after} HP")
    print(f"  Expected healing: 5 + {con_mod} = {expected_healing}")

    assert hp_after > hp_before, f"Should have healed: {hp_before} -> {hp_after}"
    assert hp_after == hp_before + expected_healing, f"Healing wrong: expected +{expected_healing}, got +{hp_after - hp_before}"
    assert "Survivor heals" in (event.status_message or ""), f"Event message should mention Survivor: {event.status_message}"

    print("  PASSED")


def test_survivor_no_heal_above_half():
    """Test Survivor does NOT heal when HP > 50%."""
    print("\nTEST: Survivor does NOT heal when HP > 50%")
    reset_state()
    get_map().create_rectangle(0, 0, 5, 5)

    fighter = create_fighter("Champion", con_score=14)
    max_hp = fighter.get_hp()

    # Apply Survivor
    survivor = Survivor(
        source_entity_uuid=fighter.uuid,
        target_entity_uuid=fighter.uuid
    )
    fighter.add_condition(survivor)

    # Damage to 60% (above 50% threshold)
    damage_to_60 = int(max_hp * 0.4)  # 40% damage = 60% HP remaining
    fighter.health.damage_taken = damage_to_60
    hp_before = fighter.get_hp()
    print(f"  HP before: {hp_before} ({int(hp_before/max_hp*100)}% of {max_hp})")

    # Trigger turn start
    fighter.on_turn_start()

    hp_after = fighter.get_hp()
    print(f"  HP after: {hp_after}")

    assert hp_after == hp_before, f"Should NOT heal above 50%: {hp_before} -> {hp_after}"

    print("  PASSED")


def test_survivor_no_heal_at_zero():
    """Test Survivor does NOT heal at 0 HP."""
    print("\nTEST: Survivor does NOT heal at 0 HP")
    reset_state()
    get_map().create_rectangle(0, 0, 5, 5)

    fighter = create_fighter("Champion", con_score=14)
    max_hp = fighter.get_hp()

    # Apply Survivor
    survivor = Survivor(
        source_entity_uuid=fighter.uuid,
        target_entity_uuid=fighter.uuid
    )
    fighter.add_condition(survivor)

    # Damage to exactly 0 HP
    fighter.health.damage_taken = max_hp
    hp_before = fighter.get_hp()
    print(f"  HP before: {hp_before} (0 HP)")

    # Trigger turn start
    fighter.on_turn_start()

    hp_after = fighter.get_hp()
    print(f"  HP after: {hp_after}")

    assert hp_after == hp_before, f"Should NOT heal at 0 HP: {hp_before} -> {hp_after}"

    print("  PASSED")


def test_survivor_with_negative_con():
    """Test Survivor with negative CON modifier (minimum 1 healing still)."""
    print("\nTEST: Survivor with negative CON modifier")
    reset_state()
    get_map().create_rectangle(0, 0, 5, 5)

    # CON 6 = -2 modifier, so healing = 5 + (-2) = 3
    fighter = create_fighter("Weak Champion", con_score=6)  # CON -2
    max_hp = fighter.get_hp()
    con_mod = fighter.ability_scores.constitution.modifier
    print(f"  CON modifier: {con_mod}")
    print(f"  Max HP: {max_hp}")

    # Apply Survivor
    survivor = Survivor(
        source_entity_uuid=fighter.uuid,
        target_entity_uuid=fighter.uuid
    )
    fighter.add_condition(survivor)

    # Damage to 50%
    fighter.health.damage_taken = max_hp // 2
    hp_before = fighter.get_hp()
    print(f"  HP before: {hp_before}")

    # Trigger turn start
    fighter.on_turn_start()

    hp_after = fighter.get_hp()
    expected_healing = 5 + con_mod  # 5 + (-2) = 3

    print(f"  HP after: {hp_after}")
    print(f"  Expected healing: 5 + {con_mod} = {expected_healing}")

    assert hp_after == hp_before + expected_healing, f"Wrong healing: expected +{expected_healing}, got +{hp_after - hp_before}"

    print("  PASSED")


def test_survivor_multiple_turns():
    """Test Survivor heals on multiple consecutive turns."""
    print("\nTEST: Survivor heals across multiple turns")
    reset_state()
    get_map().create_rectangle(0, 0, 5, 5)

    fighter = create_fighter("Champion", con_score=14)  # CON +2
    max_hp = fighter.get_hp()
    con_mod = fighter.ability_scores.constitution.modifier
    _ = 5 + con_mod  # Expected healing per turn: 7

    # Apply Survivor
    survivor = Survivor(
        source_entity_uuid=fighter.uuid,
        target_entity_uuid=fighter.uuid
    )
    fighter.add_condition(survivor)

    # Damage to 30% HP (well below 50%)
    damage_to_30 = int(max_hp * 0.7)
    fighter.health.damage_taken = damage_to_30
    print(f"  Starting HP: {fighter.get_hp()} ({int(fighter.get_hp()/max_hp*100)}%)")

    # Simulate multiple turns
    total_healed = 0
    for turn in range(3):
        hp_before = fighter.get_hp()
        current_max = hp_before + fighter.health.damage_taken  # Max HP after any healing

        # Check if still below 50%
        if hp_before <= current_max / 2:
            fighter.on_turn_start()
            hp_after = fighter.get_hp()
            healed = hp_after - hp_before
            total_healed += healed
            print(f"  Turn {turn+1}: {hp_before} -> {hp_after} (+{healed})")
        else:
            print(f"  Turn {turn+1}: HP {hp_before} is above 50%, no healing")
            # Still call turn start to verify no healing
            fighter.on_turn_start()

    print(f"  Total healed over 3 turns: {total_healed}")
    assert total_healed > 0, "Should have healed at least once"

    print("  PASSED")


def test_survivor_removal_stops_healing():
    """Test that removing Survivor condition stops the healing."""
    print("\nTEST: Removing Survivor stops healing")
    reset_state()
    get_map().create_rectangle(0, 0, 5, 5)

    fighter = create_fighter("Champion", con_score=14)
    max_hp = fighter.get_hp()

    # Apply Survivor
    survivor = Survivor(
        source_entity_uuid=fighter.uuid,
        target_entity_uuid=fighter.uuid
    )
    fighter.add_condition(survivor)
    assert "Survivor" in fighter.active_conditions

    # Damage to 50%
    fighter.health.damage_taken = max_hp // 2
    hp_before = fighter.get_hp()

    # First turn - should heal
    fighter.on_turn_start()
    hp_after_first = fighter.get_hp()
    assert hp_after_first > hp_before, "Should heal on first turn"
    print(f"  Turn 1 (with Survivor): {hp_before} -> {hp_after_first}")

    # Remove Survivor
    fighter.remove_condition("Survivor")
    assert "Survivor" not in fighter.active_conditions
    print(f"  Removed Survivor condition")

    # Damage back to 50% (reset for test)
    fighter.health.damage_taken = max_hp // 2
    hp_before_second = fighter.get_hp()

    # Second turn - should NOT heal
    fighter.on_turn_start()
    hp_after_second = fighter.get_hp()

    print(f"  Turn 2 (without Survivor): {hp_before_second} -> {hp_after_second}")
    assert hp_after_second == hp_before_second, f"Should NOT heal after Survivor removed"

    print("  PASSED")


if __name__ == "__main__":
    print("=" * 60)
    print("SURVIVOR (CHAMPION LEVEL 18) TESTS")
    print("=" * 60)

    test_survivor_heals_at_half_hp()
    test_survivor_no_heal_above_half()
    test_survivor_no_heal_at_zero()
    test_survivor_with_negative_con()
    test_survivor_multiple_turns()
    test_survivor_removal_stops_healing()

    print()
    print("=" * 60)
    print("ALL SURVIVOR TESTS PASSED")
    print("=" * 60)
