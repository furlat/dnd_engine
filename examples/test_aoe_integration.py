"""Test POSITION_AOE integration with get_available_actions."""
from uuid import uuid4

from dnd.utils import reset_combat_state
from dnd.core.gridmap import get_map
from dnd.core.aoe import Sphere
from dnd.core.base_actions import BaseAction, TargetType, Cost
from dnd.core.events import Range, RangeType
from dnd.monsters.bestiary import create_skeleton
from dnd.entity import Entity


class FireballAction(BaseAction):
    """Example AoE spell action for testing."""
    name: str = "Fireball"
    description: str = "20ft radius sphere of fire"
    target_type: TargetType = TargetType.POSITION_AOE
    template: bool = True

    def __init__(self, **data):
        # Set default aoe_shape if not provided
        # Use 10ft radius (2 tiles) for easier test positioning
        if 'aoe_shape' not in data:
            data['aoe_shape'] = Sphere(
                source_entity_uuid=data.get('source_entity_uuid', uuid4()),
                radius_feet=10
            )
        super().__init__(**data)

    def get_range(self) -> Range:
        return Range(type=RangeType.RANGE, normal=150)

    def pre_validate(self) -> bool:
        return True

    def _validate(self):
        return None  # Always valid

    def _apply(self):
        return None  # Placeholder


def test_position_aoe_in_available_actions():
    """Test that POSITION_AOE actions show affected entities."""
    print("\n=== POSITION_AOE in Available Actions ===")
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 20, 20)

    # Create caster and targets
    caster = create_skeleton(name="Caster", position=(0, 0))

    # Group of targets close together (should all be hit by 10ft radius sphere)
    # Positions within 2 tiles of (4,4) center
    _target1 = create_skeleton(name="Target1", position=(4, 4))  # Center
    _target2 = create_skeleton(name="Target2", position=(5, 4))  # 1 tile east
    _target3 = create_skeleton(name="Target3", position=(4, 5))  # 1 tile north

    # Isolated target far enough from the group (more than 2 tiles away from (4,4))
    _isolated = create_skeleton(name="Isolated", position=(9, 4))  # 5 tiles east

    Entity.update_all_entities_senses()

    # Create fireball action with cost
    fireball = FireballAction(
        source_entity_uuid=caster.uuid,
        costs=[Cost(name="Fireball", cost_type="actions", cost=1)]
    )
    caster.register_action(fireball)

    # Get available actions
    actions = caster.get_available_actions(target_filter="enemies")

    # Find the fireball action
    fireball_action = None
    for action in actions.position_actions:
        if action.template_name == "Fireball":
            fireball_action = action
            break

    assert fireball_action is not None, "Fireball action should be available"
    assert fireball_action.target_type == TargetType.POSITION_AOE, "Should be POSITION_AOE"
    print(f"✓ Fireball action found with {len(fireball_action.valid_targets)} valid target positions")

    # Find targets at (4, 4) - should show 3 affected entities (radius 20ft = 4 tiles)
    # The group at (4,4), (5,4), (4,5) are all within 4 tiles of each other
    target_at_group = None
    for target in fireball_action.valid_targets:
        if target.position == (4, 4):
            target_at_group = target
            break

    assert target_at_group is not None, "Should have target at (4, 4)"
    assert target_at_group.affected_count == 3, f"Expected 3 affected at (4,4), got {target_at_group.affected_count}"
    print(f"✓ Position (4, 4) shows {target_at_group.affected_count} affected entities")
    print(f"  Affected: {target_at_group.affected_entity_names}")

    # Find target at (9, 4) - should show only 1 affected entity (isolated)
    target_at_isolated = None
    for target in fireball_action.valid_targets:
        if target.position == (9, 4):
            target_at_isolated = target
            break

    assert target_at_isolated is not None, "Should have target at (9, 4)"
    assert target_at_isolated.affected_count == 1, f"Expected 1 affected at (9,4), got {target_at_isolated.affected_count}"
    print(f"✓ Position (9, 4) shows {target_at_isolated.affected_count} affected entity")
    print(f"  Affected: {target_at_isolated.affected_entity_names}")

    print("✓ POSITION_AOE integration test passed")


def test_entity_helper_method():
    """Test Entity.get_aoe_affected_entities helper."""
    print("\n=== Entity.get_aoe_affected_entities ===")
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 20, 20)

    caster = create_skeleton(name="Caster", position=(0, 0))  # Far from targets
    _target1 = create_skeleton(name="Target1", position=(7, 5))  # In sphere
    _target2 = create_skeleton(name="Target2", position=(15, 5))  # Outside sphere

    Entity.update_all_entities_senses()

    # Create sphere centered at (7, 5) with radius 10ft (2 tiles)
    shape = Sphere(
        source_entity_uuid=caster.uuid,
        target=(7, 5),
        radius_feet=10
    )

    positions, entities = caster.get_aoe_affected_entities(shape)

    assert len(entities) == 1, f"Expected 1 entity (Target1), got {len(entities)}: {[e.name for e in entities]}"
    assert entities[0].name == "Target1", f"Expected Target1, got {entities[0].name}"

    print(f"✓ Sphere at (7,5) radius 15ft affects {len(entities)} entity: {[e.name for e in entities]}")
    print(f"  Affected positions: {len(positions)}")

    # Caster should be excluded by default
    caster_found = any(e.uuid == caster.uuid for e in entities)
    assert not caster_found, "Caster should be excluded by default"
    print("✓ Caster correctly excluded from affected entities")

    # Test with caster included - sphere on caster's position
    _positions2, entities2 = caster.get_aoe_affected_entities(
        Sphere(source_entity_uuid=caster.uuid, target=(0, 0), radius_feet=10),  # Centered on caster
        exclude_self=False
    )
    caster_found = any(e.uuid == caster.uuid for e in entities2)
    assert caster_found, "Caster should be included with exclude_self=False"
    print("✓ Caster correctly included with exclude_self=False")

    print("✓ Entity helper method test passed")


if __name__ == "__main__":
    test_position_aoe_in_available_actions()
    test_entity_helper_method()

    print("\n" + "=" * 50)
    print("All POSITION_AOE integration tests passed!")
