#!/usr/bin/env python
"""
Test Spirit Guardians spell.

Tests:
1. Zone is created centered on caster (15ft sphere)
2. Enemy in zone on cast takes 3d8 radiant (WIS save for half)
3. Ally in zone on cast is NOT affected
4. Enemy entering zone takes damage
5. Enemy starting turn in zone takes damage
6. "Once per turn" - enemy only takes damage once per turn
7. Zone follows caster when caster moves
8. Enemy speed is halved in zone
9. Speed restored when enemy leaves zone
10. Zone is removed when concentration breaks
"""

import pytest

from dnd.utils import reset_combat_state, has_condition, get_hp, set_hp
from dnd.monsters.bestiary import create_goblin, create_caster
from dnd.entity import Entity, get_natural_roll
from dnd.spells.conjuration import SpiritGuardians, SpiritGuardiansZone
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


def test_spirit_guardians_zone_creation():
    """Test that Spirit Guardians creates a zone centered on caster."""
    print("=" * 60)
    print("TEST: Spirit Guardians Zone Creation")
    print("=" * 60)

    reset_combat_state()
    setup_arena()

    # Create caster at (10, 10)
    caster = create_caster(name="Caster", position=(10, 10), faction="heroes")
    caster.update_entity_senses(max_distance=30)

    # Cast Spirit Guardians
    spell = SpiritGuardians(
        source_entity_uuid=caster.uuid
    )

    print(f"\n1. Casting Spirit Guardians (caster at (10, 10))")
    result = spell.apply()

    print(f"   Result: {result.status_message if result else 'None'}")
    assert result is not None, "Spell should succeed"
    assert not result.canceled, "Spell should not be canceled"

    # Check concentration
    print(f"\n2. Caster concentrating: {has_condition(caster, 'Concentrating')}")
    assert has_condition(caster, "Concentrating"), "Caster should be concentrating"

    # Check zone exists
    print(f"   Zone created: {has_condition(caster, 'Spirit Guardians Zone')}")
    assert has_condition(caster, "Spirit Guardians Zone"), "Zone should be on caster"

    # Check zone center is at caster position
    zone_base = caster.active_conditions.get("Spirit Guardians Zone")
    assert zone_base is not None
    assert isinstance(zone_base, SpiritGuardiansZone)
    zone: SpiritGuardiansZone = zone_base
    print(f"\n3. Zone center: {zone.zone_center}")
    assert zone.zone_center == (10, 10), f"Zone should be centered on caster at (10, 10)"

    print("\n" + "=" * 60)
    print("PASS: Spirit Guardians zone creation works!")
    print("=" * 60)


def test_spirit_guardians_enemy_damage():
    """Test that enemies in zone on cast take damage."""
    print("\n" + "=" * 60)
    print("TEST: Spirit Guardians Enemy Damage")
    print("=" * 60)

    for attempt in range(10):
        reset_combat_state()
        setup_arena()

        caster = create_caster(name="Caster", position=(10, 10), faction="heroes")
        enemy = create_goblin(name="Enemy", position=(11, 10), faction="monsters")
        # Boost HP so goblin survives 3d8 damage
        enemy.health.max_hit_points_bonus.self_static.add_value_modifier(
            NumericalModifier.create(source_entity_uuid=enemy.uuid, name="Test HP Boost", value=90)
        )
        set_hp(enemy, 100)
        caster.update_entity_senses(max_distance=30)

        wis_save = enemy.saving_throws.get_saving_throw("wisdom")
        wis_save.bonus.self_static.add_value_modifier(
            NumericalModifier.create(
                source_entity_uuid=enemy.uuid,
                name="Test Penalty",
                value=-100
            )
        )

        initial_hp = get_hp(enemy)

        spell = SpiritGuardians(
            source_entity_uuid=caster.uuid
        )
        spell.apply()

        if had_critical_d20():
            print(f"  Attempt {attempt + 1}: got nat 1/20, retrying...")
            continue

        final_hp = get_hp(enemy)
        damage_taken = initial_hp - final_hp
        print(f"   Damage taken: {damage_taken}")

        assert damage_taken >= 3, f"Should take at least 3 damage (3d8 min), got {damage_taken}"
        assert damage_taken <= 24, f"Should take at most 24 damage (3d8 max), got {damage_taken}"

        print("PASS: Spirit Guardians enemy damage works!")
        break
    else:
        pytest.fail("Got nat 1/20 on all 10 attempts")


def test_spirit_guardians_ally_safe():
    """Test that allies in zone on cast are NOT affected."""
    print("\n" + "=" * 60)
    print("TEST: Spirit Guardians Ally Safe")
    print("=" * 60)

    reset_combat_state()
    setup_arena()

    # Create caster and ally near each other
    caster = create_caster(name="Caster", position=(10, 10), faction="heroes")
    ally = create_goblin(name="Ally", position=(11, 10), faction="heroes")  # Same faction = ally
    caster.update_entity_senses(max_distance=30)

    initial_hp = get_hp(ally)
    print(f"\n1. Ally initial HP: {initial_hp}")

    # Cast Spirit Guardians
    spell = SpiritGuardians(
        source_entity_uuid=caster.uuid
    )
    spell.apply()

    final_hp = get_hp(ally)
    print(f"   Ally HP after: {final_hp}")

    assert final_hp == initial_hp, f"Ally should not take damage, but took {initial_hp - final_hp}"

    print("\n" + "=" * 60)
    print("PASS: Spirit Guardians does not affect allies!")
    print("=" * 60)


def test_spirit_guardians_entry_damage():
    """Test that enemies entering zone take damage."""
    print("\n" + "=" * 60)
    print("TEST: Spirit Guardians Entry Damage")
    print("=" * 60)

    for attempt in range(10):
        reset_combat_state()
        setup_arena()

        caster = create_caster(name="Caster", position=(10, 10), faction="heroes")
        enemy = create_goblin(name="Enemy", position=(20, 10), faction="monsters")
        # Boost HP so goblin survives 3d8 damage
        enemy.health.max_hit_points_bonus.self_static.add_value_modifier(
            NumericalModifier.create(source_entity_uuid=enemy.uuid, name="Test HP Boost", value=90)
        )
        set_hp(enemy, 100)
        caster.update_entity_senses(max_distance=30)

        spell = SpiritGuardians(
            source_entity_uuid=caster.uuid
        )
        spell.apply()

        initial_hp = get_hp(enemy)

        wis_save = enemy.saving_throws.get_saving_throw("wisdom")
        wis_save.bonus.self_static.add_value_modifier(
            NumericalModifier.create(
                source_entity_uuid=enemy.uuid,
                name="Test Penalty",
                value=-100
            )
        )

        Entity.update_entity_position(enemy, (11, 10))

        if had_critical_d20():
            print(f"  Attempt {attempt + 1}: got nat 1/20, retrying...")
            continue

        final_hp = get_hp(enemy)
        damage_taken = initial_hp - final_hp
        print(f"   Damage taken: {damage_taken}")

        assert damage_taken >= 3, f"Should take at least 3 damage (3d8 min), got {damage_taken}"
        assert damage_taken <= 24, f"Should take at most 24 damage (3d8 max), got {damage_taken}"

        print("PASS: Spirit Guardians entry damage works!")
        break
    else:
        pytest.fail("Got nat 1/20 on all 10 attempts")


def test_spirit_guardians_once_per_turn():
    """Test that enemies only take damage once per turn."""
    print("\n" + "=" * 60)
    print("TEST: Spirit Guardians Once Per Turn")
    print("=" * 60)

    reset_combat_state()
    setup_arena()

    # Create caster and enemy
    caster = create_caster(name="Caster", position=(10, 10), faction="heroes")
    enemy = create_goblin(name="Enemy", position=(20, 10), faction="monsters")
    caster.update_entity_senses(max_distance=30)

    # Cast Spirit Guardians
    spell = SpiritGuardians(
        source_entity_uuid=caster.uuid
    )
    spell.apply()

    # Force enemy to fail WIS save
    wis_save = enemy.saving_throws.get_saving_throw("wisdom")
    wis_save.bonus.self_static.add_value_modifier(
        NumericalModifier.create(
            source_entity_uuid=enemy.uuid,
            name="Test Penalty",
            value=-100
        )
    )

    # Move enemy into zone - takes damage
    Entity.update_entity_position(enemy, (11, 10))
    hp_after_first_entry = get_hp(enemy)
    print(f"\n1. Enemy HP after first entry: {hp_after_first_entry}")

    # Check marker condition
    print(f"   Has triggered marker: {has_condition(enemy, 'Spirit Guardians Triggered')}")
    assert has_condition(enemy, "Spirit Guardians Triggered"), "Should have triggered marker"

    # Move enemy to another position in zone - should NOT take damage again
    print(f"\n2. Moving enemy to another spot in zone (12, 10)")
    Entity.update_entity_position(enemy, (12, 10))

    hp_after_second_move = get_hp(enemy)
    print(f"   Enemy HP after second move: {hp_after_second_move}")

    assert hp_after_second_move == hp_after_first_entry, "Should not take damage twice in same turn"

    print("\n" + "=" * 60)
    print("PASS: Spirit Guardians only damages once per turn!")
    print("=" * 60)


def test_spirit_guardians_follows_caster():
    """Test that zone follows caster when caster moves."""
    print("\n" + "=" * 60)
    print("TEST: Spirit Guardians Follows Caster")
    print("=" * 60)

    reset_combat_state()
    setup_arena()

    # Create caster
    caster = create_caster(name="Caster", position=(10, 10), faction="heroes")
    caster.update_entity_senses(max_distance=30)

    # Cast Spirit Guardians
    spell = SpiritGuardians(
        source_entity_uuid=caster.uuid
    )
    spell.apply()

    # Get zone
    zone_base = caster.active_conditions.get("Spirit Guardians Zone")
    assert zone_base is not None
    assert isinstance(zone_base, SpiritGuardiansZone)
    zone: SpiritGuardiansZone = zone_base

    initial_center = zone.zone_center
    print(f"\n1. Initial zone center: {initial_center}")
    assert initial_center == (10, 10)

    # Move caster
    print(f"\n2. Moving caster to (15, 15)")
    Entity.update_entity_position(caster, (15, 15))

    new_center = zone.zone_center
    print(f"   New zone center: {new_center}")

    assert new_center == (15, 15), f"Zone should follow caster to (15, 15), got {new_center}"

    print("\n" + "=" * 60)
    print("PASS: Spirit Guardians follows caster!")
    print("=" * 60)


def test_spirit_guardians_speed_halved():
    """Test that enemy speed is halved in zone."""
    print("\n" + "=" * 60)
    print("TEST: Spirit Guardians Speed Halved")
    print("=" * 60)

    reset_combat_state()
    setup_arena()

    # Create caster and enemy
    caster = create_caster(name="Caster", position=(10, 10), faction="heroes")
    enemy = create_goblin(name="Enemy", position=(20, 10), faction="monsters")
    # Boost goblin max HP so it survives 3d8 entry damage (goblin default is 10 HP)
    enemy.health.max_hit_points_bonus.self_static.add_value_modifier(
        NumericalModifier.create(source_entity_uuid=enemy.uuid, name="Test HP Boost", value=90)
    )
    set_hp(enemy, 100)
    caster.update_entity_senses(max_distance=30)

    # Get initial speed
    initial_speed = enemy.action_economy.movement.normalized_score
    print(f"\n1. Enemy initial speed: {initial_speed}")

    # Cast Spirit Guardians
    spell = SpiritGuardians(
        source_entity_uuid=caster.uuid
    )
    spell.apply()

    # Move enemy into zone
    print(f"\n2. Moving enemy into zone")
    Entity.update_entity_position(enemy, (11, 10))

    # Check slowed condition
    print(f"   Has slowed condition: {has_condition(enemy, 'Spirit Guardians Slowed')}")
    assert has_condition(enemy, "Spirit Guardians Slowed"), "Should have slowed condition"

    # Check speed
    new_speed = enemy.action_economy.movement.normalized_score
    print(f"   Enemy speed in zone: {new_speed}")

    expected_speed = initial_speed // 2
    assert new_speed == expected_speed, f"Speed should be halved ({expected_speed}), got {new_speed}"

    print("\n" + "=" * 60)
    print("PASS: Spirit Guardians halves enemy speed!")
    print("=" * 60)


def test_spirit_guardians_speed_restored():
    """Test that speed is restored when enemy leaves zone."""
    print("\n" + "=" * 60)
    print("TEST: Spirit Guardians Speed Restored on Exit")
    print("=" * 60)

    reset_combat_state()
    setup_arena()

    # Create caster and enemy
    caster = create_caster(name="Caster", position=(10, 10), faction="heroes")
    enemy = create_goblin(name="Enemy", position=(20, 10), faction="monsters")
    # Boost goblin max HP so it survives 3d8 entry damage (goblin default is 10 HP)
    enemy.health.max_hit_points_bonus.self_static.add_value_modifier(
        NumericalModifier.create(source_entity_uuid=enemy.uuid, name="Test HP Boost", value=90)
    )
    set_hp(enemy, 100)
    caster.update_entity_senses(max_distance=30)

    # Get initial speed
    initial_speed = enemy.action_economy.movement.normalized_score
    print(f"\n1. Enemy initial speed: {initial_speed}")

    # Cast Spirit Guardians
    spell = SpiritGuardians(
        source_entity_uuid=caster.uuid
    )
    spell.apply()

    # Move enemy into zone
    Entity.update_entity_position(enemy, (11, 10))
    print(f"\n2. Enemy enters zone, slowed: {has_condition(enemy, 'Spirit Guardians Slowed')}")
    assert has_condition(enemy, "Spirit Guardians Slowed")

    # Move enemy out of zone
    print(f"\n3. Moving enemy out of zone to (25, 10)")
    Entity.update_entity_position(enemy, (25, 10))

    print(f"   Has slowed condition: {has_condition(enemy, 'Spirit Guardians Slowed')}")
    assert not has_condition(enemy, "Spirit Guardians Slowed"), "Should not be slowed after leaving"

    # Check speed restored
    restored_speed = enemy.action_economy.movement.normalized_score
    print(f"   Enemy speed after leaving: {restored_speed}")

    assert restored_speed == initial_speed, f"Speed should be restored to {initial_speed}, got {restored_speed}"

    print("\n" + "=" * 60)
    print("PASS: Spirit Guardians speed restored on exit!")
    print("=" * 60)


def test_spirit_guardians_concentration_break():
    """Test that zone is removed when concentration breaks."""
    print("\n" + "=" * 60)
    print("TEST: Spirit Guardians Concentration Break")
    print("=" * 60)

    reset_combat_state()
    setup_arena()

    # Create caster
    caster = create_caster(name="Caster", position=(10, 10), faction="heroes")
    caster.update_entity_senses(max_distance=30)

    # Cast Spirit Guardians
    spell = SpiritGuardians(
        source_entity_uuid=caster.uuid
    )
    spell.apply()

    print(f"\n1. Zone active: {has_condition(caster, 'Spirit Guardians Zone')}")
    print(f"   Concentrating: {has_condition(caster, 'Concentrating')}")
    assert has_condition(caster, "Spirit Guardians Zone")
    assert has_condition(caster, "Concentrating")

    # Break concentration
    print(f"\n2. Breaking concentration...")
    caster.remove_condition("Concentrating")

    print(f"   Zone active: {has_condition(caster, 'Spirit Guardians Zone')}")
    print(f"   Concentrating: {has_condition(caster, 'Concentrating')}")

    assert not has_condition(caster, "Concentrating"), "Should not be concentrating"
    assert not has_condition(caster, "Spirit Guardians Zone"), "Zone should be removed"

    print("\n" + "=" * 60)
    print("PASS: Zone removed when concentration breaks!")
    print("=" * 60)


if __name__ == "__main__":
    test_spirit_guardians_zone_creation()
    test_spirit_guardians_enemy_damage()
    test_spirit_guardians_ally_safe()
    test_spirit_guardians_entry_damage()
    test_spirit_guardians_once_per_turn()
    test_spirit_guardians_follows_caster()
    test_spirit_guardians_speed_halved()
    test_spirit_guardians_speed_restored()
    test_spirit_guardians_concentration_break()
    print("\n" + "=" * 60)
    print("ALL SPIRIT GUARDIANS TESTS PASSED!")
    print("=" * 60)
