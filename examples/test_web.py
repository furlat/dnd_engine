#!/usr/bin/env python
"""
Test Web spell.

Tests:
1. Zone is created with difficult terrain
2. Creature in zone on cast must DEX save or restrained
3. Creature entering zone must DEX save or restrained
4. Restrained creature can escape with STR (Athletics) check
5. Zone is removed when concentration breaks
"""

from dnd.utils import reset_combat_state, has_condition
from dnd.monsters.bestiary import create_skeleton
from dnd.entity import Entity
from dnd.spells.conjuration import Web
from dnd.core.gridmap import get_map, reset_map
from dnd.core.modifiers import NumericalModifier


def setup_arena(size: int = 20):
    """Set up a simple floor arena for testing."""
    reset_map()
    grid = get_map()
    for x in range(size):
        for y in range(size):
            grid.set_tile(x, y, walkable=True, name="Floor")
    return grid


def test_web_zone_creation():
    """Test that Web creates a zone with difficult terrain."""
    print("=" * 60)
    print("TEST: Web Zone Creation")
    print("=" * 60)

    reset_combat_state()
    setup_arena()

    # Create caster
    caster = create_skeleton(name="Caster", position=(0, 0))
    caster.update_entity_senses(max_distance=20)

    # Cast Web at position (5, 5)
    target_pos = (5, 5)
    spell = Web(
        source_entity_uuid=caster.uuid,
        end_position=target_pos
    )

    print(f"\n1. Casting Web at {target_pos}")
    result = spell.apply()

    print(f"   Result: {result.status_message if result else 'None'}")
    assert result is not None, "Spell should succeed"
    assert not result.canceled, "Spell should not be canceled"

    # Check concentration
    print(f"\n2. Caster concentrating: {has_condition(caster, 'Concentrating')}")
    assert has_condition(caster, "Concentrating"), "Caster should be concentrating"

    # Check zone exists
    print(f"   Zone created: {has_condition(caster, 'Web Zone')}")
    assert has_condition(caster, "Web Zone"), "Zone should be on caster"

    # Check difficult terrain
    grid = get_map()
    center_tile = grid.get_tile(5, 5)
    if center_tile:
        walking_cost = center_tile.walking_cost.normalized_score
        print(f"\n3. Tile (5,5) walking cost: {walking_cost}")
        assert walking_cost == 2, f"Should be difficult terrain (cost=2), got {walking_cost}"

    print("\n" + "=" * 60)
    print("PASS: Web zone creation works!")
    print("=" * 60)


def test_web_entry_restrained():
    """Test that entering the zone causes DEX save or restrained."""
    print("\n" + "=" * 60)
    print("TEST: Web Entry Causes Restrained")
    print("=" * 60)

    reset_combat_state()
    setup_arena()

    # Create caster and target
    caster = create_skeleton(name="Caster", position=(0, 0))
    target = create_skeleton(name="Target", position=(10, 5))  # Outside zone
    caster.update_entity_senses(max_distance=20)

    # Cast Web
    target_pos = (5, 5)
    spell = Web(
        source_entity_uuid=caster.uuid,
        end_position=target_pos
    )
    spell.apply()

    print(f"\n1. Target initial state:")
    print(f"   Restrained: {has_condition(target, 'Restrained')}")
    print(f"   Web Restrained: {has_condition(target, 'Web Restrained')}")
    assert not has_condition(target, "Web Restrained"), "Target should not start restrained"

    # Force target to fail DEX save
    dex_save = target.saving_throws.get_saving_throw("dexterity")
    dex_save.bonus.self_static.add_value_modifier(
        NumericalModifier.create(
            source_entity_uuid=target.uuid,
            name="Test Penalty",
            value=-100
        )
    )

    # Move target into the zone
    print(f"\n2. Moving target into zone at (5, 5)")
    Entity.update_entity_position(target, (5, 5))

    print(f"   Web Restrained: {has_condition(target, 'Web Restrained')}")
    print(f"   Restrained (sub-condition): {has_condition(target, 'Restrained')}")
    assert has_condition(target, "Web Restrained"), "Target should be web restrained"
    assert has_condition(target, "Restrained"), "Target should have Restrained sub-condition"

    print("\n" + "=" * 60)
    print("PASS: Web entry causes restrained on failed save!")
    print("=" * 60)


def test_web_escape_action():
    """Test that restrained creature can escape with STR check."""
    print("\n" + "=" * 60)
    print("TEST: Web Escape Action")
    print("=" * 60)

    reset_combat_state()
    setup_arena()

    # Create caster and target already in zone
    caster = create_skeleton(name="Caster", position=(0, 0))
    target = create_skeleton(name="Target", position=(5, 5))  # In zone
    caster.update_entity_senses(max_distance=20)

    # Force target to fail DEX save
    dex_save = target.saving_throws.get_saving_throw("dexterity")
    dex_save.bonus.self_static.add_value_modifier(
        NumericalModifier.create(
            source_entity_uuid=target.uuid,
            name="Test Penalty",
            value=-100
        )
    )

    # Cast Web
    target_pos = (5, 5)
    spell = Web(
        source_entity_uuid=caster.uuid,
        end_position=target_pos
    )
    spell.apply()

    print(f"\n1. Target in zone, Web Restrained: {has_condition(target, 'Web Restrained')}")
    assert has_condition(target, "Web Restrained")

    # Check escape action is available
    available = target.get_available_actions()
    action_names = [a.template_name for a in available.all_actions]
    print(f"   Available actions: {action_names}")
    assert "Escape Web" in action_names, "Escape Web action should be available"

    # Give target a massive Athletics bonus to ensure success
    athletics = target.skill_set.get_skill("athletics")
    athletics.skill_bonus.self_static.add_value_modifier(
        NumericalModifier.create(
            source_entity_uuid=target.uuid,
            name="Test Bonus",
            value=100
        )
    )

    # Use the escape action
    print(f"\n2. Using Escape Web action...")
    from dnd.actions_functional import execute_action
    from dnd.core.base_actions import AvailableTarget
    escape_target = AvailableTarget(index=0)  # Self-targeting action
    result = execute_action(target, "Escape Web", escape_target)

    print(f"   Result: {result.status_message if result else 'None'}")
    print(f"\n3. After escape:")
    print(f"   Web Restrained: {has_condition(target, 'Web Restrained')}")
    print(f"   Restrained: {has_condition(target, 'Restrained')}")

    assert not has_condition(target, "Web Restrained"), "Should no longer be web restrained"
    assert not has_condition(target, "Restrained"), "Restrained sub-condition should be removed"

    print("\n" + "=" * 60)
    print("PASS: Web escape action works!")
    print("=" * 60)


def test_web_escape_failure():
    """Test that failed escape keeps creature restrained."""
    print("\n" + "=" * 60)
    print("TEST: Web Escape Failure")
    print("=" * 60)

    reset_combat_state()
    setup_arena()

    # Create caster and target already in zone
    caster = create_skeleton(name="Caster", position=(0, 0))
    target = create_skeleton(name="Target", position=(5, 5))  # In zone
    caster.update_entity_senses(max_distance=20)

    # Force target to fail DEX save
    dex_save = target.saving_throws.get_saving_throw("dexterity")
    dex_save.bonus.self_static.add_value_modifier(
        NumericalModifier.create(
            source_entity_uuid=target.uuid,
            name="Test Penalty",
            value=-100
        )
    )

    # Cast Web
    target_pos = (5, 5)
    spell = Web(
        source_entity_uuid=caster.uuid,
        end_position=target_pos
    )
    spell.apply()

    print(f"\n1. Target Web Restrained: {has_condition(target, 'Web Restrained')}")
    assert has_condition(target, "Web Restrained")

    # Give target a massive Athletics penalty to ensure failure
    athletics = target.skill_set.get_skill("athletics")
    athletics.skill_bonus.self_static.add_value_modifier(
        NumericalModifier.create(
            source_entity_uuid=target.uuid,
            name="Test Penalty",
            value=-100
        )
    )

    # Use the escape action
    print(f"\n2. Using Escape Web action (should fail)...")
    from dnd.actions_functional import execute_action
    from dnd.core.base_actions import AvailableTarget
    escape_target = AvailableTarget(index=0)
    result = execute_action(target, "Escape Web", escape_target)

    print(f"   Result: {result.status_message if result else 'None'}")
    print(f"\n3. After failed escape:")
    print(f"   Web Restrained: {has_condition(target, 'Web Restrained')}")
    print(f"   Restrained: {has_condition(target, 'Restrained')}")

    assert has_condition(target, "Web Restrained"), "Should still be web restrained"
    assert has_condition(target, "Restrained"), "Should still have Restrained"

    print("\n" + "=" * 60)
    print("PASS: Web escape failure keeps creature restrained!")
    print("=" * 60)


def test_web_concentration_break():
    """Test that zone is removed when concentration breaks."""
    print("\n" + "=" * 60)
    print("TEST: Web Concentration Break")
    print("=" * 60)

    reset_combat_state()
    setup_arena()

    # Create caster
    caster = create_skeleton(name="Caster", position=(0, 0))
    caster.update_entity_senses(max_distance=20)

    # Cast Web
    target_pos = (5, 5)
    spell = Web(
        source_entity_uuid=caster.uuid,
        end_position=target_pos
    )
    spell.apply()

    print(f"\n1. Zone active: {has_condition(caster, 'Web Zone')}")
    print(f"   Concentrating: {has_condition(caster, 'Concentrating')}")
    assert has_condition(caster, "Web Zone")
    assert has_condition(caster, "Concentrating")

    # Break concentration
    print(f"\n2. Breaking concentration...")
    caster.remove_condition("Concentrating")

    print(f"   Zone active: {has_condition(caster, 'Web Zone')}")
    print(f"   Concentrating: {has_condition(caster, 'Concentrating')}")

    assert not has_condition(caster, "Concentrating"), "Should not be concentrating"
    assert not has_condition(caster, "Web Zone"), "Zone should be removed"

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
    test_web_zone_creation()
    test_web_entry_restrained()
    test_web_escape_action()
    test_web_escape_failure()
    test_web_concentration_break()
    print("\n" + "=" * 60)
    print("ALL WEB TESTS PASSED!")
    print("=" * 60)
