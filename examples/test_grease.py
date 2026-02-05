#!/usr/bin/env python
"""
Test Grease spell.

Tests:
1. Zone is created with difficult terrain
2. Creature in zone on cast must DEX save or fall prone
3. Creature entering zone must DEX save or fall prone
4. Creature starting turn in zone must DEX save or fall prone
5. Zone is removed when concentration breaks
"""

from dnd.utils import reset_combat_state, has_condition
from dnd.monsters.bestiary import create_skeleton
from dnd.entity import Entity
from dnd.spells.conjuration import Grease
from dnd.core.gridmap import get_map, reset_map


def setup_arena(size: int = 20):
    """Set up a simple floor arena for testing."""
    reset_map()
    grid = get_map()
    for x in range(size):
        for y in range(size):
            grid.set_tile(x, y, walkable=True, name="Floor")
    return grid


def test_grease_zone_creation():
    """Test that Grease creates a zone with difficult terrain."""
    print("=" * 60)
    print("TEST: Grease Zone Creation")
    print("=" * 60)

    reset_combat_state()
    setup_arena()

    # Create caster
    caster = create_skeleton(name="Caster", position=(0, 0))
    caster.update_entity_senses(max_distance=20)

    # Cast Grease at position (5, 5)
    target_pos = (5, 5)
    spell = Grease(
        source_entity_uuid=caster.uuid,
        end_position=target_pos
    )

    print(f"\n1. Casting Grease at {target_pos}")
    result = spell.apply()

    print(f"   Result: {result.status_message if result else 'None'}")
    assert result is not None, "Spell should succeed"
    assert not result.canceled, "Spell should not be canceled"

    # Check concentration
    print(f"\n2. Caster concentrating: {has_condition(caster, 'Concentrating')}")
    assert has_condition(caster, "Concentrating"), "Caster should be concentrating"

    # Check zone exists
    print(f"   Zone created: {has_condition(caster, 'Grease Zone')}")
    assert has_condition(caster, "Grease Zone"), "Zone should be on caster"

    # Check difficult terrain
    grid = get_map()
    center_tile = grid.get_tile(5, 5)
    if center_tile:
        walking_cost = center_tile.walking_cost.normalized_score
        print(f"\n3. Tile (5,5) walking cost: {walking_cost}")
        assert walking_cost == 2, f"Should be difficult terrain (cost=2), got {walking_cost}"

    print("\n" + "=" * 60)
    print("PASS: Grease zone creation works!")
    print("=" * 60)


def test_grease_entry_prone():
    """Test that entering the zone causes DEX save or prone."""
    print("\n" + "=" * 60)
    print("TEST: Grease Entry Causes Prone")
    print("=" * 60)

    reset_combat_state()
    setup_arena()

    # Create caster and target
    caster = create_skeleton(name="Caster", position=(0, 0))
    target = create_skeleton(name="Target", position=(10, 5))  # Outside zone
    caster.update_entity_senses(max_distance=20)

    # Give target terrible DEX to ensure fail (use force_attack_miss pattern)
    # Actually, let's just run the test multiple times - statistically should fail sometimes
    # For deterministic test, we'll apply -100 to DEX save

    # Cast Grease
    target_pos = (5, 5)
    spell = Grease(
        source_entity_uuid=caster.uuid,
        end_position=target_pos
    )
    spell.apply()

    print(f"\n1. Target initial state: Prone={has_condition(target, 'Prone')}")
    assert not has_condition(target, "Prone"), "Target should not start prone"

    # Force target to fail DEX save by giving them massive penalty
    from dnd.core.modifiers import NumericalModifier
    dex_save = target.saving_throws.get_saving_throw("dexterity")
    _penalty_uuid = dex_save.bonus.self_static.add_value_modifier(
        NumericalModifier.create(
            source_entity_uuid=target.uuid,
            name="Test Penalty",
            value=-100
        )
    )

    # Move target into the zone
    print(f"\n2. Moving target into zone at (5, 5)")
    Entity.update_entity_position(target, (5, 5))

    print(f"   Target Prone after entering: {has_condition(target, 'Prone')}")
    assert has_condition(target, "Prone"), "Target should be prone after failing DEX save"

    print("\n" + "=" * 60)
    print("PASS: Grease entry causes prone on failed save!")
    print("=" * 60)


def test_grease_turn_start_prone():
    """Test that starting turn in zone causes DEX save - with BG3 auto-stand behavior."""
    print("\n" + "=" * 60)
    print("TEST: Grease Turn Start (BG3 Auto-Stand)")
    print("=" * 60)

    reset_combat_state()
    setup_arena()

    # Create caster and target already in zone area
    caster = create_skeleton(name="Caster", position=(0, 0))
    target = create_skeleton(name="Target", position=(5, 5))  # In zone area
    caster.update_entity_senses(max_distance=20)

    # Cast Grease - target should be affected immediately
    target_pos = (5, 5)
    spell = Grease(
        source_entity_uuid=caster.uuid,
        end_position=target_pos
    )

    # Force target to fail DEX save
    from dnd.core.modifiers import NumericalModifier
    dex_save = target.saving_throws.get_saving_throw("dexterity")
    dex_save.bonus.self_static.add_value_modifier(
        NumericalModifier.create(
            source_entity_uuid=target.uuid,
            name="Test Penalty",
            value=-100
        )
    )

    print(f"\n1. Casting Grease - target at (5,5) in zone")
    result = spell.apply()
    print(f"   Result: {result.status_message if result else 'None'}")

    # Target should be prone from initial cast (not their turn yet)
    print(f"\n2. Target Prone after cast: {has_condition(target, 'Prone')}")
    assert has_condition(target, "Prone"), "Target should be prone from being in zone on cast"

    # Remove Prone (simulating previous auto-stand)
    target.remove_condition("Prone")
    print(f"\n3. Removed Prone. Target Prone: {has_condition(target, 'Prone')}")
    assert not has_condition(target, "Prone")

    # Trigger turn start - BG3 behavior: Grease causes Prone but they immediately stand
    print(f"\n4. Target starts their turn in the zone")
    target.on_turn_start()

    # With BG3 auto-stand: they fall prone but immediately stand (consuming movement)
    print(f"   Target Prone after turn start: {has_condition(target, 'Prone')}")
    print(f"   Target movement: {target.action_economy.movement.normalized_score}ft")

    # BG3 style: NOT prone (auto-stood), but movement consumed (30 - 15 = 15)
    assert not has_condition(target, "Prone"), "Should NOT be prone (BG3 auto-stand)"
    assert target.action_economy.movement.normalized_score == 15, \
        f"Should have 15ft movement (30 - 15 auto-stand cost), got {target.action_economy.movement.normalized_score}"

    print("\n" + "=" * 60)
    print("PASS: Grease turn start triggers prone + auto-stand!")
    print("=" * 60)


def test_grease_turn_start_no_movement():
    """Test that entity stays prone if no movement available during turn start."""
    print("\n" + "=" * 60)
    print("TEST: Grease Turn Start (No Movement - Stays Prone)")
    print("=" * 60)

    reset_combat_state()
    setup_arena()

    # Create caster and target
    caster = create_skeleton(name="Caster", position=(0, 0))
    target = create_skeleton(name="Target", position=(5, 5))
    caster.update_entity_senses(max_distance=20)

    # Cast Grease
    spell = Grease(
        source_entity_uuid=caster.uuid,
        end_position=(5, 5)
    )

    # Force target to fail DEX save
    from dnd.core.modifiers import NumericalModifier
    dex_save = target.saving_throws.get_saving_throw("dexterity")
    dex_save.bonus.self_static.add_value_modifier(
        NumericalModifier.create(
            source_entity_uuid=target.uuid,
            name="Test Penalty",
            value=-100
        )
    )

    spell.apply()

    # Start target's turn, then consume all remaining movement
    target.on_turn_start()  # Reset movement to full (30ft)

    # If target became prone from turn start in zone, they auto-stood (15ft consumed)
    # Remove any Prone if present and consume remaining movement
    if has_condition(target, "Prone"):
        target.remove_condition("Prone")

    remaining = target.action_economy.movement.normalized_score
    target.action_economy.consume("movement", remaining)  # Consume all remaining movement

    print(f"\n1. Target movement before prone: {target.action_economy.movement.normalized_score}ft")
    assert target.action_economy.movement.normalized_score == 0

    # Apply Prone during own turn but with no movement
    print(f"\n2. Applying Prone during own turn with no movement...")
    from dnd.conditions import Prone
    prone = Prone(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=target.uuid
    )
    target.add_condition(prone)

    print(f"   Target Prone: {has_condition(target, 'Prone')}")
    assert has_condition(target, "Prone"), "Should be prone (no movement to auto-stand)"

    print("\n" + "=" * 60)
    print("PASS: No movement = stays prone!")
    print("=" * 60)


def test_grease_not_own_turn():
    """Test that entity stays prone when knocked down outside their turn."""
    print("\n" + "=" * 60)
    print("TEST: Grease Not Own Turn (Stays Prone)")
    print("=" * 60)

    reset_combat_state()
    setup_arena()

    # Create caster and target
    caster = create_skeleton(name="Caster", position=(0, 0))
    target = create_skeleton(name="Target", position=(10, 10))  # Outside zone initially
    caster.update_entity_senses(max_distance=20)

    # Cast Grease
    spell = Grease(
        source_entity_uuid=caster.uuid,
        end_position=(5, 5)
    )
    spell.apply()

    # Force target to fail DEX save
    from dnd.core.modifiers import NumericalModifier
    dex_save = target.saving_throws.get_saving_throw("dexterity")
    dex_save.bonus.self_static.add_value_modifier(
        NumericalModifier.create(
            source_entity_uuid=target.uuid,
            name="Test Penalty",
            value=-100
        )
    )

    print(f"\n1. Target is_my_turn: {target.is_my_turn}")
    assert not target.is_my_turn, "Should NOT be target's turn"

    # Move target into zone (not their turn)
    print(f"\n2. Moving target into Grease zone (not their turn)")
    from dnd.entity import Entity
    Entity.update_entity_position(target, (5, 5))

    print(f"   Target Prone: {has_condition(target, 'Prone')}")
    assert has_condition(target, "Prone"), "Should be prone (not their turn, can't auto-stand)"

    print("\n" + "=" * 60)
    print("PASS: Not own turn = stays prone!")
    print("=" * 60)


def test_grease_concentration_break():
    """Test that zone is removed when concentration breaks."""
    print("\n" + "=" * 60)
    print("TEST: Grease Concentration Break")
    print("=" * 60)

    reset_combat_state()
    setup_arena()

    # Create caster
    caster = create_skeleton(name="Caster", position=(0, 0))
    caster.update_entity_senses(max_distance=20)

    # Cast Grease
    target_pos = (5, 5)
    spell = Grease(
        source_entity_uuid=caster.uuid,
        end_position=target_pos
    )
    spell.apply()

    print(f"\n1. Zone active: {has_condition(caster, 'Grease Zone')}")
    print(f"   Concentrating: {has_condition(caster, 'Concentrating')}")
    assert has_condition(caster, "Grease Zone")
    assert has_condition(caster, "Concentrating")

    # Break concentration
    print(f"\n2. Breaking concentration...")
    caster.remove_condition("Concentrating")

    print(f"   Zone active: {has_condition(caster, 'Grease Zone')}")
    print(f"   Concentrating: {has_condition(caster, 'Concentrating')}")

    assert not has_condition(caster, "Concentrating"), "Should not be concentrating"
    assert not has_condition(caster, "Grease Zone"), "Zone should be removed"

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
    test_grease_zone_creation()
    test_grease_entry_prone()
    test_grease_turn_start_prone()
    test_grease_turn_start_no_movement()
    test_grease_not_own_turn()
    test_grease_concentration_break()
    print("\n" + "=" * 60)
    print("ALL GREASE TESTS PASSED!")
    print("=" * 60)
