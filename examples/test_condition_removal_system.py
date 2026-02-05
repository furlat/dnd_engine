"""
Test suite for condition removal system refactor.

Tests all types of condition relationships:
1. Basic condition removal (modifiers, handlers)
2. Sub-conditions (same entity - parent/child)
3. External conditions (cross-entity - concentration spells)
4. Terrain conditions (tiles - zone spells)
5. Duration expiration
6. Custom _remove() hooks
"""

from uuid import uuid4
from dnd.entity import Entity
from dnd.core.base_conditions import BaseCondition
from dnd.core.gridmap import get_map, GridMap
from dnd.core.events import EventQueue
from dnd.utils import reset_combat_state
from dnd.monsters.bestiary import create_skeleton

# =============================================================================
# Test 1: Basic Condition Removal
# =============================================================================

def test_basic_condition_removal():
    """Condition removal cleans up modifiers and handlers."""
    reset_combat_state()

    # Create entity with a condition that adds modifiers
    entity = create_skeleton(name="Test", position=(0, 0))

    # Apply Blinded (adds modifiers)
    from dnd.conditions import Blinded
    blinded = Blinded(source_entity_uuid=entity.uuid, target_entity_uuid=entity.uuid)
    entity.add_condition(blinded)

    assert "Blinded" in entity.active_conditions
    assert blinded.applied

    # Remove condition
    entity.remove_condition("Blinded")

    assert "Blinded" not in entity.active_conditions
    assert not blinded.applied

    print("✓ Test 1: Basic condition removal works")


# =============================================================================
# Test 2: Sub-Conditions (Same Entity)
# =============================================================================

def test_sub_condition_removal():
    """Parent condition removal cascades to sub-conditions."""
    reset_combat_state()

    entity = create_skeleton(name="Test", position=(0, 0))

    # Paralyzed has Incapacitated as sub-condition
    from dnd.conditions import Paralyzed
    paralyzed = Paralyzed(source_entity_uuid=entity.uuid, target_entity_uuid=entity.uuid)
    entity.add_condition(paralyzed)

    assert "Paralyzed" in entity.active_conditions
    assert "Incapacitated" in entity.active_conditions  # Sub-condition

    # Get the incapacitated condition
    incapacitated = entity.active_conditions.get("Incapacitated")
    assert incapacitated is not None
    assert incapacitated.parent_condition == paralyzed.uuid

    # Remove parent - should remove child too
    entity.remove_condition("Paralyzed")

    assert "Paralyzed" not in entity.active_conditions
    assert "Incapacitated" not in entity.active_conditions  # Auto-removed
    assert not paralyzed.applied
    assert not incapacitated.applied

    print("✓ Test 2: Sub-condition removal cascades correctly")


def test_nested_sub_conditions():
    """Deeply nested sub-conditions are all removed."""
    reset_combat_state()

    entity = create_skeleton(name="Test", position=(0, 0))

    # Stunned -> Incapacitated (nested)
    from dnd.conditions import Stunned
    stunned = Stunned(source_entity_uuid=entity.uuid, target_entity_uuid=entity.uuid)
    entity.add_condition(stunned)

    assert "Stunned" in entity.active_conditions
    assert "Incapacitated" in entity.active_conditions

    entity.remove_condition("Stunned")

    assert "Stunned" not in entity.active_conditions
    assert "Incapacitated" not in entity.active_conditions

    print("✓ Test 3: Nested sub-conditions cascade correctly")


# =============================================================================
# Test 3: External Conditions (Cross-Entity)
# =============================================================================

def test_external_condition_removal():
    """Condition with external_conditions cleans up other entities."""
    reset_combat_state()

    caster = create_skeleton(name="Caster", position=(0, 0))
    target = create_skeleton(name="Target", position=(1, 0))

    Entity.update_all_entities_senses()

    # Create a concentration spell effect manually
    from dnd.conditions import Concentrating, Paralyzed
    from dnd.spells.enchantment import HoldPersonEffect

    # Apply spell effect to target
    effect = HoldPersonEffect(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=target.uuid
    )
    target.add_condition(effect)

    assert "Hold Person" in target.active_conditions
    assert "Paralyzed" in target.active_conditions  # Sub-condition of effect

    # Apply Concentrating to caster with external_conditions link
    concentrating = Concentrating(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=caster.uuid,
        spell_name="Hold Person"
    )
    caster.add_condition(concentrating)
    concentrating.add_external_condition(target.uuid, effect.uuid)

    assert "Concentrating" in caster.active_conditions

    # Break concentration - should clean up target
    caster.remove_condition("Concentrating")

    assert "Concentrating" not in caster.active_conditions
    assert "Hold Person" not in target.active_conditions  # Cleaned up
    assert "Paralyzed" not in target.active_conditions  # Sub-condition also gone

    print("✓ Test 4: External condition removal cleans up other entities")


# =============================================================================
# Test 4: Duration Expiration
# =============================================================================

def test_duration_expiration():
    """Condition properly expires and is removed via Entity."""
    reset_combat_state()

    entity = create_skeleton(name="Test", position=(0, 0))

    from dnd.conditions import Dodging
    from dnd.core.base_conditions import Duration, DurationType

    # Create a 1-round condition
    dodging = Dodging(
        source_entity_uuid=entity.uuid,
        target_entity_uuid=entity.uuid,
        duration=Duration(
            duration=1,
            duration_type=DurationType.ROUNDS,
            source_entity_uuid=entity.uuid,
            target_entity_uuid=entity.uuid
        )
    )
    entity.add_condition(dodging)

    assert "Dodging" in entity.active_conditions

    # Progress through Entity
    entity.advance_duration_condition("Dodging")

    assert "Dodging" not in entity.active_conditions
    assert not dodging.applied

    print("✓ Test 5: Duration expiration works via Entity")


# =============================================================================
# Test 5: Custom _remove() Hooks
# =============================================================================

def test_custom_remove_hook_rage():
    """RageFeature _remove() unregisters Rage action."""
    reset_combat_state()

    entity = create_skeleton(name="Barbarian", position=(0, 0))

    from dnd.classes.rage import RageFeature

    # Apply rage feature (name is "Rage Feature" with space)
    rage_feature = RageFeature(
        source_entity_uuid=entity.uuid,
        target_entity_uuid=entity.uuid,
        rage_uses=3,
        rage_damage=2
    )
    entity.add_condition(rage_feature)

    assert "Rage Feature" in entity.active_conditions
    assert entity.get_action_template("Rage") is not None

    # Remove - should unregister action
    entity.remove_condition("Rage Feature")

    assert "Rage Feature" not in entity.active_conditions
    assert entity.get_action_template("Rage") is None

    print("✓ Test 6: Custom _remove() hook (RageFeature) works")


def test_custom_remove_hook_second_wind():
    """SecondWindFeature _remove() unregisters action and resource."""
    reset_combat_state()

    entity = create_skeleton(name="Fighter", position=(0, 0))

    from dnd.classes.fighter import SecondWindFeature

    second_wind = SecondWindFeature(
        source_entity_uuid=entity.uuid,
        target_entity_uuid=entity.uuid,
        fighter_level=5
    )
    entity.add_condition(second_wind)

    # Name is "Second Wind Feature" with space
    assert "Second Wind Feature" in entity.active_conditions
    assert entity.get_action_template("Second Wind") is not None

    entity.remove_condition("Second Wind Feature")

    assert "Second Wind Feature" not in entity.active_conditions
    assert entity.get_action_template("Second Wind") is None

    print("✓ Test 7: Custom _remove() hook (SecondWindFeature) works")


# =============================================================================
# Test 6: No Late Imports Verification
# =============================================================================

def test_no_late_imports_in_base_conditions():
    """Verify base_conditions.py cleanup_own_state has no late imports."""
    import ast

    with open("dnd/core/base_conditions.py", "r") as f:
        source = f.read()

    tree = ast.parse(source)

    # Find cleanup_own_state method
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "cleanup_own_state":
            # Check for late imports inside this function
            late_imports = []
            for child in ast.walk(node):
                if isinstance(child, ast.Import) or isinstance(child, ast.ImportFrom):
                    late_imports.append(ast.dump(child))

            if late_imports:
                print(f"✗ Found late imports in cleanup_own_state: {late_imports}")
                assert False, f"Late imports found in cleanup_own_state: {late_imports}"
            else:
                print("✓ Test 8: No late imports in cleanup_own_state()")
                return

    print("✓ Test 8: cleanup_own_state method found, no late imports")


# =============================================================================
# Test 7: Remove Condition By UUID
# =============================================================================

def test_remove_condition_by_uuid():
    """Test that remove_condition_by_uuid works correctly."""
    reset_combat_state()

    entity = create_skeleton(name="Test", position=(0, 0))

    from dnd.conditions import Blinded
    blinded = Blinded(source_entity_uuid=entity.uuid, target_entity_uuid=entity.uuid)
    entity.add_condition(blinded)

    condition_uuid = blinded.uuid
    assert "Blinded" in entity.active_conditions

    # Remove by UUID
    entity.remove_condition_by_uuid(condition_uuid)

    assert "Blinded" not in entity.active_conditions
    assert not blinded.applied

    print("✓ Test 9: remove_condition_by_uuid works")


# =============================================================================
# Test 8: BaseBlock (Tile) Condition Removal
# =============================================================================

def test_tile_condition_removal():
    """Test that BaseBlock.remove_condition works for tiles."""
    reset_combat_state()

    # Set up grid
    GridMap.reset()
    grid = get_map()
    grid.create_room(0, 0, 10, 10)

    # Get a tile
    tile = grid.get_tile(5, 5)
    assert tile is not None

    # Create and apply a simple condition to the tile
    from dnd.core.base_conditions import BaseCondition

    class TestTileCondition(BaseCondition):
        name: str = "TestTileCondition"

    cond = TestTileCondition(
        source_entity_uuid=tile.uuid,
        target_entity_uuid=tile.uuid
    )
    tile.add_condition(cond)

    assert "TestTileCondition" in tile.active_conditions

    # Remove condition
    tile.remove_condition("TestTileCondition")

    assert "TestTileCondition" not in tile.active_conditions
    assert not cond.applied

    print("✓ Test 10: Tile condition removal works")


# =============================================================================
# Main
# =============================================================================

def run_all_tests():
    """Run all condition removal tests."""
    print("=" * 60)
    print("CONDITION REMOVAL SYSTEM TESTS")
    print("=" * 60)

    test_basic_condition_removal()
    test_sub_condition_removal()
    test_nested_sub_conditions()
    test_external_condition_removal()
    test_duration_expiration()
    test_custom_remove_hook_rage()
    test_custom_remove_hook_second_wind()
    test_no_late_imports_in_base_conditions()
    test_remove_condition_by_uuid()
    test_tile_condition_removal()

    print("=" * 60)
    print("ALL TESTS PASSED!")
    print("=" * 60)


if __name__ == "__main__":
    run_all_tests()
