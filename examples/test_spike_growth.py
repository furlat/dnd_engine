#!/usr/bin/env python
"""
Test Spike Growth spell.

Tests:
1. Zone is created with difficult terrain
2. Entity takes 2d4 damage when entering zone
3. Caster doesn't take damage in own zone
4. Zone is removed when concentration breaks
"""

from dnd.utils import reset_combat_state, has_condition, get_hp
from dnd.monsters.bestiary import create_skeleton, create_sorcerer
from dnd.entity import Entity
from dnd.spells.transmutation import SpikeGrowth
from dnd.core.gridmap import get_map, reset_map


def setup_arena(size: int = 20):
    """Set up a simple floor arena for testing."""
    reset_map()
    grid = get_map()
    for x in range(size):
        for y in range(size):
            grid.set_tile(x, y, walkable=True, name="Floor")
    return grid


def test_spike_growth_zone_creation():
    """Test that Spike Growth creates a zone with difficult terrain."""
    print("=" * 60)
    print("TEST: Spike Growth Zone Creation")
    print("=" * 60)

    reset_combat_state()
    setup_arena()

    # Create caster
    caster = create_sorcerer(name="Caster", position=(0, 0))
    # Update senses with larger range to see the target position
    caster.update_entity_senses(max_distance=20)

    # Cast Spike Growth at position (5, 5) - within 150ft range
    target_pos = (5, 5)
    spell = SpikeGrowth(
        source_entity_uuid=caster.uuid,
        end_position=target_pos
    )

    print(f"\n1. Casting Spike Growth at {target_pos}")
    result = spell.apply()

    print(f"   Result: {result.status_message if result else 'None'}")
    assert result is not None, "Spell should succeed"
    assert not result.canceled, "Spell should not be canceled"

    # Check concentration
    print(f"\n2. Caster concentrating: {has_condition(caster, 'Concentrating')}")
    assert has_condition(caster, "Concentrating"), "Caster should be concentrating"

    # Check zone exists
    print(f"   Zone created: {has_condition(caster, 'Spike Growth Zone')}")
    assert has_condition(caster, "Spike Growth Zone"), "Zone should be on caster"

    # Check difficult terrain
    grid = get_map()
    center_tile = grid.get_tile(5, 5)
    if center_tile:
        walking_cost = center_tile.walking_cost.normalized_score
        print(f"\n3. Tile (5,5) walking cost: {walking_cost}")
        assert walking_cost == 2, f"Should be difficult terrain (cost=2), got {walking_cost}"

    print("\n" + "=" * 60)
    print("PASS: Spike Growth zone creation works!")
    print("=" * 60)


def test_spike_growth_entry_damage():
    """Test that entering the zone deals 2d4 damage."""
    print("\n" + "=" * 60)
    print("TEST: Spike Growth Entry Damage")
    print("=" * 60)

    reset_combat_state()
    setup_arena()

    # Create caster and target
    caster = create_sorcerer(name="Caster", position=(0, 0))
    target = create_skeleton(name="Target", position=(10, 5))  # Outside zone
    caster.update_entity_senses(max_distance=20)

    initial_hp = get_hp(target)
    print(f"\n1. Target initial HP: {initial_hp}")

    # Cast Spike Growth at position (5, 5)
    target_pos = (5, 5)
    spell = SpikeGrowth(
        source_entity_uuid=caster.uuid,
        end_position=target_pos
    )
    spell.apply()

    # Move target into the zone
    print(f"\n2. Moving target into zone at (5, 5)")
    Entity.update_entity_position(target, (5, 5))

    final_hp = get_hp(target)
    damage_taken = initial_hp - final_hp
    print(f"   Target HP after: {final_hp}")
    print(f"   Damage taken: {damage_taken}")

    # 2d4 = 2-8 damage
    assert damage_taken >= 2, f"Should take at least 2 damage (2d4 min), got {damage_taken}"
    assert damage_taken <= 8, f"Should take at most 8 damage (2d4 max), got {damage_taken}"

    print("\n" + "=" * 60)
    print("PASS: Spike Growth entry damage works!")
    print("=" * 60)


def test_spike_growth_caster_immune():
    """Test that caster doesn't take damage in own zone."""
    print("\n" + "=" * 60)
    print("TEST: Spike Growth Caster Immunity")
    print("=" * 60)

    reset_combat_state()
    setup_arena()

    # Create caster
    caster = create_sorcerer(name="Caster", position=(0, 0))
    caster.update_entity_senses(max_distance=20)

    initial_hp = get_hp(caster)
    print(f"\n1. Caster initial HP: {initial_hp}")

    # Cast Spike Growth at position (5, 5)
    target_pos = (5, 5)
    spell = SpikeGrowth(
        source_entity_uuid=caster.uuid,
        end_position=target_pos
    )
    spell.apply()

    # Move caster into the zone
    print(f"\n2. Moving caster into their own zone")
    Entity.update_entity_position(caster, (5, 5))

    final_hp = get_hp(caster)
    print(f"   Caster HP after: {final_hp}")

    assert final_hp == initial_hp, f"Caster should not take damage in own zone"

    print("\n" + "=" * 60)
    print("PASS: Caster doesn't take damage in own zone!")
    print("=" * 60)


def test_spike_growth_concentration_break():
    """Test that zone is removed when concentration breaks."""
    print("\n" + "=" * 60)
    print("TEST: Spike Growth Concentration Break")
    print("=" * 60)

    reset_combat_state()
    setup_arena()

    # Create caster
    caster = create_sorcerer(name="Caster", position=(0, 0))
    caster.update_entity_senses(max_distance=20)

    # Cast Spike Growth
    target_pos = (5, 5)
    spell = SpikeGrowth(
        source_entity_uuid=caster.uuid,
        end_position=target_pos
    )
    spell.apply()

    print(f"\n1. Zone active: {has_condition(caster, 'Spike Growth Zone')}")
    print(f"   Concentrating: {has_condition(caster, 'Concentrating')}")
    assert has_condition(caster, "Spike Growth Zone")
    assert has_condition(caster, "Concentrating")

    # Break concentration by removing the condition
    print(f"\n2. Breaking concentration...")
    caster.remove_condition("Concentrating")

    print(f"   Zone active: {has_condition(caster, 'Spike Growth Zone')}")
    print(f"   Concentrating: {has_condition(caster, 'Concentrating')}")

    assert not has_condition(caster, "Concentrating"), "Should not be concentrating"
    assert not has_condition(caster, "Spike Growth Zone"), "Zone should be removed"

    # Check terrain is restored
    grid = get_map()
    center_tile = grid.get_tile(5, 5)
    if center_tile:
        walking_cost = center_tile.walking_cost.normalized_score
        print(f"\n3. Tile (5,5) walking cost after: {walking_cost}")
        assert walking_cost == 1, f"Should be normal terrain (cost=1), got {walking_cost}"

    print("\n" + "=" * 60)
    print("PASS: Zone removed when concentration breaks!")
    print("=" * 60)


if __name__ == "__main__":
    test_spike_growth_zone_creation()
    test_spike_growth_entry_damage()
    test_spike_growth_caster_immune()
    test_spike_growth_concentration_break()
    print("\n" + "=" * 60)
    print("ALL SPIKE GROWTH TESTS PASSED!")
    print("=" * 60)
