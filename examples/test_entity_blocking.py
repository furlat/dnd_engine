"""
Test entity blocking via the polymorphic blocks_walking() interface.

Validates:
1. Alive entity blocks walking for others
2. Alive entity does NOT block its own path (self-avoidance)
3. Dead entity does NOT block walking (corpse walkability)
4. GridMap.is_walkable_for() uses polymorphic dispatch
5. Pathfinding avoids alive entities but routes through dead ones
6. BaseBlock.get() returns Entity and dispatches correctly
"""

from dnd.utils.test_utils import reset_combat_state, has_condition, deal_damage_to
from dnd.core.gridmap import get_map
from dnd.core.base_block import BaseBlock
from dnd.monsters.bestiary import create_skeleton
from dnd.entity import Entity
from dnd.core.modifiers import DamageType


def test_entity_blocks_walking_for_others():
    """Alive entity at a position blocks other entities."""
    print("\n=== Test: Entity Blocks Walking For Others ===")
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 10, 10)

    entity_a = create_skeleton(name="Skeleton A", position=(5, 5))
    entity_b = create_skeleton(name="Skeleton B", position=(5, 6))
    Entity.update_all_entities_senses()

    # entity_a should block walking for entity_b
    assert entity_a.blocks_walking(requesting_entity_uuid=entity_b.uuid) is True, \
        "Alive entity should block walking for others"

    # GridMap should report (5,5) as not walkable for entity_b
    assert grid.is_walkable_for(5, 5, requesting_entity_uuid=entity_b.uuid) is False, \
        "Occupied cell should not be walkable for other entity"

    print("  PASS: Alive entity blocks walking for others")


def test_entity_does_not_block_self():
    """Entity does not block its own position."""
    print("\n=== Test: Entity Does Not Block Self ===")
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 10, 10)

    entity = create_skeleton(name="Skeleton", position=(5, 5))
    Entity.update_all_entities_senses()

    # Entity should NOT block itself
    assert entity.blocks_walking(requesting_entity_uuid=entity.uuid) is False, \
        "Entity should not block its own position"

    # GridMap should report (5,5) as walkable for the entity itself
    assert grid.is_walkable_for(5, 5, requesting_entity_uuid=entity.uuid) is True, \
        "Entity's own cell should be walkable for itself"

    print("  PASS: Entity does not block its own position")


def test_dead_entity_does_not_block():
    """Dead entity (corpse) does not block walking."""
    print("\n=== Test: Dead Entity Does Not Block ===")
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 10, 10)

    entity_a = create_skeleton(name="Skeleton A", position=(5, 5))
    entity_b = create_skeleton(name="Skeleton B", position=(5, 7))
    Entity.update_all_entities_senses()

    # Kill entity_a by dealing massive damage
    deal_damage_to(entity_a, 999, DamageType.BLUDGEONING, entity_b.uuid)

    assert has_condition(entity_a, "Dead"), "Entity A should be dead"

    # Dead entity should NOT block walking
    assert entity_a.blocks_walking(requesting_entity_uuid=entity_b.uuid) is False, \
        "Dead entity should not block walking"

    # GridMap should report dead entity's cell as walkable
    assert grid.is_walkable_for(5, 5, requesting_entity_uuid=entity_b.uuid) is True, \
        "Cell with dead entity should be walkable"

    print("  PASS: Dead entity does not block walking")


def test_move_through_dead_body():
    """Entity can path through a cell containing a dead body."""
    print("\n=== Test: Move Through Dead Body ===")
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 10, 10)

    # A is between B's start and a target position
    entity_a = create_skeleton(name="Blocker", position=(5, 5))
    entity_b = create_skeleton(name="Mover", position=(5, 7))
    Entity.update_all_entities_senses()

    # While alive, (5,5) should NOT be in B's paths
    assert (5, 5) not in entity_b.senses.paths, \
        "Alive blocker's cell should not be in paths"

    # Kill entity_a
    deal_damage_to(entity_a, 999, DamageType.BLUDGEONING, entity_b.uuid)
    assert has_condition(entity_a, "Dead"), "Entity A should be dead"

    # Update senses - now B should be able to path through (5,5)
    Entity.update_all_entities_senses()

    assert (5, 5) in entity_b.senses.paths, \
        "Dead body's cell should now be pathable"

    print("  PASS: Can path through dead body")


def test_polymorphic_dispatch_via_baseblock():
    """BaseBlock.get(entity_uuid) returns Entity, blocks_walking dispatches correctly."""
    print("\n=== Test: Polymorphic Dispatch Via BaseBlock ===")
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 10, 10)

    entity = create_skeleton(name="Skeleton", position=(5, 5))
    other = create_skeleton(name="Other", position=(5, 7))
    Entity.update_all_entities_senses()

    # BaseBlock.get should return the Entity
    block = BaseBlock.get(entity.uuid)
    assert block is entity, "BaseBlock.get(entity.uuid) should return the entity itself"

    # blocks_walking via BaseBlock reference should use Entity override
    assert block is not None
    assert block.blocks_walking(requesting_entity_uuid=other.uuid) is True, \
        "Polymorphic dispatch should use Entity.blocks_walking()"
    assert block.blocks_walking(requesting_entity_uuid=entity.uuid) is False, \
        "Polymorphic dispatch should handle self-avoidance"

    print("  PASS: Polymorphic dispatch works correctly")


def test_no_requesting_uuid_blocks_on_occupied():
    """Without requesting_entity_uuid, occupied cell is blocked."""
    print("\n=== Test: No Requesting UUID Blocks On Occupied ===")
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 10, 10)

    create_skeleton(name="Skeleton", position=(5, 5))
    Entity.update_all_entities_senses()

    # With no requesting entity, an occupied cell should be blocked
    assert grid.is_walkable_for(5, 5, requesting_entity_uuid=None) is False, \
        "Occupied cell should not be walkable with no requesting entity"

    # Empty cell should still be walkable
    assert grid.is_walkable_for(6, 6, requesting_entity_uuid=None) is True, \
        "Empty cell should be walkable with no requesting entity"

    print("  PASS: No requesting UUID blocks on occupied cell")


if __name__ == "__main__":
    test_entity_blocks_walking_for_others()
    test_entity_does_not_block_self()
    test_dead_entity_does_not_block()
    test_move_through_dead_body()
    test_polymorphic_dispatch_via_baseblock()
    test_no_requesting_uuid_blocks_on_occupied()
    print("\n=== ALL ENTITY BLOCKING TESTS PASSED ===")
