#!/usr/bin/env python
"""
Test Cloudkill spell.

Tests:
1. Zone is created (20ft sphere, no difficult terrain)
2. Creature in zone on cast takes 5d8 poison (CON save for half)
3. Creature entering zone takes damage
4. Creature starting turn in zone takes damage
5. Zone moves 10ft away from caster at caster's turn start
6. Zone is removed when concentration breaks
"""

import pytest

from dnd.utils import reset_combat_state, has_condition, get_hp
from dnd.monsters.bestiary import create_goblin, create_sorcerer
from dnd.entity import Entity, get_natural_roll
from dnd.spells.conjuration import Cloudkill
from dnd.core.gridmap import get_map, reset_map
from dnd.core.modifiers import NumericalModifier
from dnd.core.events import EventQueue


def had_critical_d20() -> bool:
    """Check if any d20 roll in the current EventQueue had a nat 1 or nat 20."""
    for event in EventQueue._all_events:
        for attr in ('dice_roll', 'save_roll'):
            roll = getattr(event, attr, None)
            if roll is not None:
                try:
                    nat = get_natural_roll(roll)
                    if nat in (1, 20):
                        return True
                except Exception:
                    pass
    return False


def setup_arena(size: int = 30):
    """Set up a simple floor arena for testing."""
    reset_map()
    grid = get_map()
    for x in range(size):
        for y in range(size):
            grid.set_tile(x, y, walkable=True, name="Floor")
    return grid


def test_cloudkill_zone_creation():
    """Test that Cloudkill creates a zone (no difficult terrain)."""
    print("=" * 60)
    print("TEST: Cloudkill Zone Creation")
    print("=" * 60)

    reset_combat_state()
    setup_arena()

    # Create caster
    caster = create_sorcerer(name="Caster", position=(0, 0))
    caster.update_entity_senses(max_distance=30)

    # Cast Cloudkill at position (10, 10)
    target_pos = (10, 10)
    spell = Cloudkill(
        source_entity_uuid=caster.uuid,
        end_position=target_pos
    )

    print(f"\n1. Casting Cloudkill at {target_pos}")
    result = spell.apply()

    print(f"   Result: {result.status_message if result else 'None'}")
    assert result is not None, "Spell should succeed"
    assert not result.canceled, "Spell should not be canceled"

    # Check concentration
    print(f"\n2. Caster concentrating: {has_condition(caster, 'Concentrating')}")
    assert has_condition(caster, "Concentrating"), "Caster should be concentrating"

    # Check zone exists
    print(f"   Zone created: {has_condition(caster, 'Cloudkill Zone')}")
    assert has_condition(caster, "Cloudkill Zone"), "Zone should be on caster"

    # Check NO difficult terrain (Cloudkill just obscures)
    grid = get_map()
    center_tile = grid.get_tile(10, 10)
    if center_tile:
        walking_cost = center_tile.walking_cost.normalized_score
        print(f"\n3. Tile (10,10) walking cost: {walking_cost}")
        assert walking_cost == 1, f"Should be normal terrain (cost=1), got {walking_cost}"

    print("\n" + "=" * 60)
    print("PASS: Cloudkill zone creation works!")
    print("=" * 60)


def test_cloudkill_initial_damage():
    """Test that creatures in zone on cast take damage."""
    print("\n" + "=" * 60)
    print("TEST: Cloudkill Initial Damage")
    print("=" * 60)
    print("   Note: Using goblins (not immune to poison)")

    for attempt in range(10):
        reset_combat_state()
        setup_arena()

        caster = create_sorcerer(name="Caster", position=(0, 0))
        target = create_goblin(name="Target", position=(10, 10))
        caster.update_entity_senses(max_distance=30)

        con_save = target.saving_throws.get_saving_throw("constitution")
        con_save.bonus.self_static.add_value_modifier(
            NumericalModifier.create(
                source_entity_uuid=target.uuid,
                name="Test Penalty",
                value=-100
            )
        )

        initial_hp = get_hp(target)
        print(f"\n1. Target initial HP: {initial_hp}")

        target_pos = (10, 10)
        spell = Cloudkill(
            source_entity_uuid=caster.uuid,
            end_position=target_pos
        )
        spell.apply()

        if had_critical_d20():
            print(f"  Attempt {attempt + 1}: got nat 1/20, retrying...")
            continue

        final_hp = get_hp(target)
        damage_taken = initial_hp - final_hp
        print(f"   Damage taken: {damage_taken}")

        assert damage_taken >= 5, f"Should take at least 5 damage (5d8 min), got {damage_taken}"
        assert damage_taken <= 40, f"Should take at most 40 damage (5d8 max), got {damage_taken}"

        print("PASS: Cloudkill initial damage works!")
        break
    else:
        pytest.fail("Got nat 1/20 on all 10 attempts")


def test_cloudkill_entry_damage():
    """Test that entering the zone deals damage."""
    print("\n" + "=" * 60)
    print("TEST: Cloudkill Entry Damage")
    print("=" * 60)
    print("   Note: Using goblins (not immune to poison)")

    for attempt in range(10):
        reset_combat_state()
        setup_arena()

        caster = create_sorcerer(name="Caster", position=(0, 0))
        target = create_goblin(name="Target", position=(20, 10))
        caster.update_entity_senses(max_distance=30)

        target_pos = (10, 10)
        spell = Cloudkill(
            source_entity_uuid=caster.uuid,
            end_position=target_pos
        )
        spell.apply()

        initial_hp = get_hp(target)

        con_save = target.saving_throws.get_saving_throw("constitution")
        con_save.bonus.self_static.add_value_modifier(
            NumericalModifier.create(
                source_entity_uuid=target.uuid,
                name="Test Penalty",
                value=-100
            )
        )

        Entity.update_entity_position(target, (10, 10))

        if had_critical_d20():
            print(f"  Attempt {attempt + 1}: got nat 1/20, retrying...")
            continue

        final_hp = get_hp(target)
        damage_taken = initial_hp - final_hp
        print(f"   Damage taken: {damage_taken}")

        assert damage_taken >= 5, f"Should take at least 5 damage (5d8 min), got {damage_taken}"
        assert damage_taken <= 40, f"Should take at most 40 damage (5d8 max), got {damage_taken}"

        print("PASS: Cloudkill entry damage works!")
        break
    else:
        pytest.fail("Got nat 1/20 on all 10 attempts")


def test_cloudkill_turn_start_damage():
    """Test that starting turn in zone deals damage."""
    print("\n" + "=" * 60)
    print("TEST: Cloudkill Turn Start Damage")
    print("=" * 60)
    print("   Note: Using goblins (not immune to poison)")

    for attempt in range(10):
        reset_combat_state()
        setup_arena()

        caster = create_sorcerer(name="Caster", position=(0, 0))
        target = create_goblin(name="Target", position=(20, 10))
        caster.update_entity_senses(max_distance=30)

        target_pos = (10, 10)
        spell = Cloudkill(
            source_entity_uuid=caster.uuid,
            end_position=target_pos
        )
        spell.apply()

        Entity.update_entity_position(target, (10, 10))

        hp_before_turn = get_hp(target)

        con_save = target.saving_throws.get_saving_throw("constitution")
        con_save.bonus.self_static.add_value_modifier(
            NumericalModifier.create(
                source_entity_uuid=target.uuid,
                name="Test Penalty",
                value=-100
            )
        )

        target.on_turn_start()

        if had_critical_d20():
            print(f"  Attempt {attempt + 1}: got nat 1/20, retrying...")
            continue

        final_hp = get_hp(target)
        damage_taken = hp_before_turn - final_hp
        print(f"   Damage taken: {damage_taken}")

        assert damage_taken >= 5, f"Should take at least 5 damage (5d8 min), got {damage_taken}"
        assert damage_taken <= 40, f"Should take at most 40 damage (5d8 max), got {damage_taken}"

        print("PASS: Cloudkill turn start damage works!")
        break
    else:
        pytest.fail("Got nat 1/20 on all 10 attempts")


def test_cloudkill_auto_move():
    """Test that zone moves 10ft away from caster at caster's turn start."""
    print("\n" + "=" * 60)
    print("TEST: Cloudkill Auto-Move")
    print("=" * 60)

    reset_combat_state()
    setup_arena()

    # Create caster at origin
    caster = create_sorcerer(name="Caster", position=(0, 0))
    caster.update_entity_senses(max_distance=30)

    # Cast Cloudkill at position (10, 0) - directly right of caster
    target_pos = (10, 0)
    spell = Cloudkill(
        source_entity_uuid=caster.uuid,
        end_position=target_pos
    )
    spell.apply()

    # Get zone condition
    from dnd.spells.conjuration import CloudkillZone
    zone_base = caster.active_conditions.get("Cloudkill Zone")
    assert zone_base is not None, "Zone should exist"
    assert isinstance(zone_base, CloudkillZone), "Zone should be CloudkillZone"
    zone: CloudkillZone = zone_base

    initial_center = zone.zone_center
    print(f"\n1. Initial zone center: {initial_center}")
    assert initial_center == (10, 0), f"Zone should be at (10, 0), got {initial_center}"

    # Trigger caster's turn start
    print(f"\n2. Caster starts their turn (zone should move away)")
    caster.on_turn_start()

    new_center = zone.zone_center
    print(f"   New zone center: {new_center}")

    # Zone should move 10ft (2 tiles) away from caster
    # Since caster is at (0,0) and zone was at (10,0), it should move further right
    expected_x = 12  # 10 + 2 tiles
    assert new_center[0] >= initial_center[0], f"Zone should move away from caster (right)"
    assert new_center[0] == expected_x, f"Zone should move to x={expected_x}, got {new_center[0]}"

    print("\n" + "=" * 60)
    print("PASS: Cloudkill auto-move works!")
    print("=" * 60)


def test_cloudkill_concentration_break():
    """Test that zone is removed when concentration breaks."""
    print("\n" + "=" * 60)
    print("TEST: Cloudkill Concentration Break")
    print("=" * 60)

    reset_combat_state()
    setup_arena()

    # Create caster
    caster = create_sorcerer(name="Caster", position=(0, 0))
    caster.update_entity_senses(max_distance=30)

    # Cast Cloudkill
    target_pos = (10, 10)
    spell = Cloudkill(
        source_entity_uuid=caster.uuid,
        end_position=target_pos
    )
    spell.apply()

    print(f"\n1. Zone active: {has_condition(caster, 'Cloudkill Zone')}")
    print(f"   Concentrating: {has_condition(caster, 'Concentrating')}")
    assert has_condition(caster, "Cloudkill Zone")
    assert has_condition(caster, "Concentrating")

    # Break concentration
    print(f"\n2. Breaking concentration...")
    caster.remove_condition("Concentrating")

    print(f"   Zone active: {has_condition(caster, 'Cloudkill Zone')}")
    print(f"   Concentrating: {has_condition(caster, 'Concentrating')}")

    assert not has_condition(caster, "Concentrating"), "Should not be concentrating"
    assert not has_condition(caster, "Cloudkill Zone"), "Zone should be removed"

    print("\n" + "=" * 60)
    print("PASS: Zone removed when concentration breaks!")
    print("=" * 60)


if __name__ == "__main__":
    test_cloudkill_zone_creation()
    test_cloudkill_initial_damage()
    test_cloudkill_entry_damage()
    test_cloudkill_turn_start_damage()
    test_cloudkill_auto_move()
    test_cloudkill_concentration_break()
    print("\n" + "=" * 60)
    print("ALL CLOUDKILL TESTS PASSED!")
    print("=" * 60)
