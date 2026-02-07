"""
Items System Phase 1 Integration Tests

Tests: BaseItem, GridMap objects, Senses.objects, Inventory, Entity loot/drop,
PickUpAction, AttackObjectAction, get_available_actions OBJECT discovery,
environment step for floor item conditions.
"""

import sys
import traceback
from uuid import uuid4

from dnd.utils import reset_combat_state
from dnd.core.gridmap import get_map
from dnd.core.base_block import BaseBlock
from dnd.core.modifiers import DamageType
from dnd.core.base_conditions import BaseCondition, DurationType
from dnd.blocks.base_item import BaseItem, EquippableItem, UsableItem, ItemRarity
from dnd.blocks.inventory import Inventory
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.entity import Entity, EntityConfig
from dnd.blocks.abilities import AbilityScoresConfig, AbilityConfig
from dnd.blocks.equipment import EquipmentConfig, WeaponSlot
from dnd.blocks.action_economy import ActionEconomyConfig
from dnd.actions_functional import setup_standard_actions, execute_by_index
from dnd.items.weapons import create_longsword

tests_passed = 0
tests_failed = 0


def run_test(name, func):
    global tests_passed, tests_failed
    reset_combat_state()
    try:
        func()
        print(f"  PASS: {name}")
        tests_passed += 1
    except Exception:
        print(f"  FAIL: {name}")
        traceback.print_exc()
        tests_failed += 1


def create_test_entity(position=(3, 3), name="Hero", faction="heroes"):
    """Create a simple entity for testing."""
    source_id = uuid4()
    config = EntityConfig(
        ability_scores=AbilityScoresConfig(
            strength=AbilityConfig(ability_score=16),
            dexterity=AbilityConfig(ability_score=14),
        ),
        health=HealthConfig(hit_dices=[HitDiceConfig(hit_dice_value=10, hit_dice_count=5, mode="maximums")]),
        equipment=EquipmentConfig(),
        action_economy=ActionEconomyConfig(),
        proficiency_bonus=2,
        position=position,
        faction=faction,
    )
    entity = Entity.create(name=name, source_entity_uuid=source_id, config=config)
    # Equip a weapon so AttackObject can work
    sword = create_longsword(entity.uuid)
    entity.equipment.equip(sword, WeaponSlot.MELEE_MAIN)
    setup_standard_actions(entity)
    return entity


def create_test_grid():
    """Create a simple 10x10 floor grid."""
    grid = get_map()
    grid.create_rectangle(0, 0, 10, 10)
    return grid


def create_simple_item(position=None, name="Potion", pickable=True):
    """Create a simple pickable item."""
    item = BaseItem(
        source_entity_uuid=uuid4(),
        name=name,
        is_pickable=pickable,
        weight=1.0,
        value=50,
    )
    if position is not None:
        get_map().place_object(item.uuid, position)
    return item


def create_breakable_item(position=None, name="Crate", hp=20):
    """Create a breakable targetable item."""
    source_id = uuid4()
    health = BaseItem.create_item_health(source_id, hp)
    item = BaseItem(
        source_entity_uuid=source_id,
        name=name,
        is_pickable=False,
        is_targetable=True,
        health=health,
        weight=50.0,
    )
    if position is not None:
        get_map().place_object(item.uuid, position)
    return item


# =========================================================================
# Test 1: BaseItem fields and spatial
# =========================================================================
def test_base_item_fields():
    item = BaseItem(source_entity_uuid=uuid4(), name="Test Item", weight=5.0, value=100, rarity=ItemRarity.RARE)
    assert item.name == "Test Item"
    assert item.weight == 5.0
    assert item.value == 100
    assert item.rarity == ItemRarity.RARE
    assert item.is_pickable is True
    assert item.is_equippable is False
    assert item.is_usable is False
    assert item.blocks_walking() is False
    assert item.blocks_vision() is False

    # Test blocking item
    blocker = BaseItem(source_entity_uuid=uuid4(), name="Boulder", blocks_movement=True, blocks_vision_field=True)
    assert blocker.blocks_walking() is True
    assert blocker.blocks_vision() is True


def test_equippable_usable_stubs():
    eq = EquippableItem(source_entity_uuid=uuid4(), name="Ring")
    assert eq.is_equippable is True
    assert eq.is_pickable is True

    us = UsableItem(source_entity_uuid=uuid4(), name="Scroll")
    assert us.is_usable is True


# =========================================================================
# Test 2: BaseItem damage via Health block
# =========================================================================
def test_item_health_damage():
    source_id = uuid4()
    health = BaseItem.create_item_health(source_id, hp=16, hit_dice_value=8)
    item = BaseItem(
        source_entity_uuid=source_id,
        name="Barrel",
        is_targetable=True,
        health=health,
    )
    assert item.is_breakable() is True
    max_hp = item.get_max_hp()
    assert max_hp == 16  # 2 * 8 = 16 (maximums mode)
    assert item.get_hp() == max_hp

    # Deal damage
    actual = item.receive_damage(5, DamageType.SLASHING, uuid4())
    assert actual == 5
    assert item.get_hp() == max_hp - 5


def test_item_health_resistances():
    source_id = uuid4()
    health = BaseItem.create_item_health(
        source_id, hp=16, hit_dice_value=8,
        immunities=[DamageType.POISON, DamageType.PSYCHIC],
        vulnerabilities=[DamageType.FIRE],
    )
    item = BaseItem(
        source_entity_uuid=source_id,
        name="Wooden Crate",
        is_targetable=True,
        health=health,
    )
    max_hp = item.get_max_hp()

    # Poison immunity - 0 damage
    actual = item.receive_damage(10, DamageType.POISON, uuid4())
    assert actual == 0
    assert item.get_hp() == max_hp

    # Fire vulnerability - double damage
    actual = item.receive_damage(4, DamageType.FIRE, uuid4())
    assert actual == 8  # 4 * 2 = 8
    assert item.get_hp() == max_hp - 8


def test_item_destruction():
    """Item destroyed at 0 HP — removed from grid and registry."""
    grid = create_test_grid()
    item = create_breakable_item(position=(5, 5), hp=8)
    item_uuid = item.uuid
    assert grid.get_object_position(item_uuid) == (5, 5)
    assert BaseBlock.get(item_uuid) is not None

    # Kill it
    item.receive_damage(100, DamageType.BLUDGEONING, uuid4())
    assert grid.get_object_position(item_uuid) is None
    assert BaseBlock.get(item_uuid) is None


# =========================================================================
# Test 3: GridMap object placement
# =========================================================================
def test_gridmap_place_remove():
    grid = create_test_grid()
    item = BaseItem(source_entity_uuid=uuid4(), name="Key")
    item_uuid = item.uuid

    grid.place_object(item_uuid, (2, 3))
    assert grid.get_object_position(item_uuid) == (2, 3)
    assert item_uuid in grid.get_objects_at((2, 3))

    grid.remove_object(item_uuid)
    assert grid.get_object_position(item_uuid) is None
    assert item_uuid not in grid.get_objects_at((2, 3))


def test_gridmap_clear():
    grid = create_test_grid()
    item = BaseItem(source_entity_uuid=uuid4(), name="Gem")
    grid.place_object(item.uuid, (1, 1))
    grid.clear()
    assert grid.get_object_position(item.uuid) is None


# =========================================================================
# Test 4: GridMap predicates with objects
# =========================================================================
def test_blocking_object_walkability():
    grid = create_test_grid()
    boulder = BaseItem(source_entity_uuid=uuid4(), name="Boulder", blocks_movement=True)
    grid.place_object(boulder.uuid, (5, 5))

    # Position should NOT be walkable for entities
    assert grid.is_walkable_for(5, 5) is False
    # But tile itself is still walkable (no entity blocks)
    assert grid.is_walkable(5, 5) is True


def test_blocking_object_vision():
    grid = create_test_grid()
    wall_obj = BaseItem(source_entity_uuid=uuid4(), name="Barricade", blocks_vision_field=True)
    grid.place_object(wall_obj.uuid, (5, 5))

    assert grid.is_blocking(5, 5) is True


# =========================================================================
# Test 5: Senses discovers objects
# =========================================================================
def test_senses_objects():
    create_test_grid()
    item = create_simple_item(position=(4, 3))
    entity = create_test_entity(position=(3, 3))
    Entity.update_all_entities_senses()

    assert item.uuid in entity.senses.objects
    assert entity.senses.objects[item.uuid] == (4, 3)


def test_senses_objects_removed():
    grid = create_test_grid()
    item = create_simple_item(position=(4, 3))
    entity = create_test_entity(position=(3, 3))
    Entity.update_all_entities_senses()
    assert item.uuid in entity.senses.objects

    # Remove object and update senses
    grid.remove_object(item.uuid)
    Entity.update_all_entities_senses()
    assert item.uuid not in entity.senses.objects


# =========================================================================
# Test 6: Inventory operations
# =========================================================================
def test_inventory_add_remove():
    inv = Inventory(source_entity_uuid=uuid4())
    item = BaseItem(source_entity_uuid=uuid4(), name="Potion", weight=0.5)

    assert inv.add_item(item) is True
    assert inv.has_item(item.uuid) is True
    assert inv.item_count == 1
    assert inv.total_weight == 0.5

    removed = inv.remove_item(item.uuid)
    assert removed is item
    assert inv.item_count == 0


def test_inventory_capacity():
    inv = Inventory(source_entity_uuid=uuid4(), max_slots=2, weight_capacity=5.0)
    item1 = BaseItem(source_entity_uuid=uuid4(), name="A", weight=2.0)
    item2 = BaseItem(source_entity_uuid=uuid4(), name="B", weight=2.0)
    item3 = BaseItem(source_entity_uuid=uuid4(), name="C", weight=2.0)

    assert inv.add_item(item1) is True
    assert inv.add_item(item2) is True
    # Slot limit reached
    assert inv.add_item(item3) is False

    # Weight limit
    inv2 = Inventory(source_entity_uuid=uuid4(), weight_capacity=3.0)
    heavy = BaseItem(source_entity_uuid=uuid4(), name="Heavy", weight=5.0)
    assert inv2.add_item(heavy) is False


def test_inventory_transfer():
    inv1 = Inventory(source_entity_uuid=uuid4())
    inv2 = Inventory(source_entity_uuid=uuid4())
    item = BaseItem(source_entity_uuid=uuid4(), name="Gem")

    inv1.add_item(item)
    assert inv1.transfer_to(item.uuid, inv2) is True
    assert inv1.has_item(item.uuid) is False
    assert inv2.has_item(item.uuid) is True


def test_inventory_find():
    inv = Inventory(source_entity_uuid=uuid4())
    p1 = BaseItem(source_entity_uuid=uuid4(), name="Potion", tags=["consumable"])
    p2 = BaseItem(source_entity_uuid=uuid4(), name="Potion", tags=["consumable"])
    s1 = BaseItem(source_entity_uuid=uuid4(), name="Sword", tags=["weapon"])
    inv.add_item(p1)
    inv.add_item(p2)
    inv.add_item(s1)

    assert len(inv.find_items_by_name("Potion")) == 2
    assert len(inv.find_items_by_tag("weapon")) == 1


# =========================================================================
# Test 7: Entity loot/drop
# =========================================================================
def test_entity_loot_item():
    grid = create_test_grid()
    item = create_simple_item(position=(3, 4))
    entity = create_test_entity(position=(3, 3))
    Entity.update_all_entities_senses()

    assert grid.get_object_position(item.uuid) == (3, 4)
    result = entity.loot_item(item)
    assert result is True
    assert entity.inventory.has_item(item.uuid) is True
    assert grid.get_object_position(item.uuid) is None


def test_entity_drop_item():
    grid = create_test_grid()
    entity = create_test_entity(position=(3, 3))
    item = BaseItem(source_entity_uuid=uuid4(), name="Gem", weight=0.1)
    entity.inventory.add_item(item)

    dropped = entity.drop_item(item.uuid)
    assert dropped is item
    assert entity.inventory.has_item(item.uuid) is False
    assert grid.get_object_position(item.uuid) == (3, 3)


# =========================================================================
# Test 8: Lifecycle hooks
# =========================================================================
def test_lifecycle_hooks():
    class TrackingItem(BaseItem):
        looted: bool = False
        dropped: bool = False
        destroyed: bool = False

        def _on_loot(self, entity_uuid, inventory_uuid):
            self.looted = True

        def _on_drop(self, entity_uuid, position):
            self.dropped = True

        def _on_destroy(self):
            self.destroyed = True

    grid = create_test_grid()
    item = TrackingItem(source_entity_uuid=uuid4(), name="Tracked")
    grid.place_object(item.uuid, (4, 4))

    entity = create_test_entity(position=(3, 3))
    Entity.update_all_entities_senses()

    entity.loot_item(item)
    assert item.looted is True

    entity.drop_item(item.uuid)
    assert item.dropped is True

    # Make it breakable and destroy
    item.is_targetable = True
    item.health = BaseItem.create_item_health(item.source_entity_uuid, 8)
    item.receive_damage(100, DamageType.BLUDGEONING, uuid4())
    assert item.destroyed is True


# =========================================================================
# Test 9: PickUpAction via get_available_actions
# =========================================================================
def test_pickup_available_actions():
    create_test_grid()
    create_simple_item(position=(4, 3), name="Gold Coin")
    entity = create_test_entity(position=(3, 3))
    Entity.update_all_entities_senses()

    available = entity.get_available_actions()
    # Find Pick Up in object_actions
    pickup_actions = [a for a in available.object_actions if a.template_name == "Pick Up"]
    assert len(pickup_actions) == 1, f"Expected 1 Pick Up action, got {len(pickup_actions)}"
    assert len(pickup_actions[0].valid_targets) == 1
    assert pickup_actions[0].valid_targets[0].target_name == "Gold Coin"


def test_pickup_execute():
    grid = create_test_grid()
    item = create_simple_item(position=(4, 3), name="Gem")
    entity = create_test_entity(position=(3, 3))
    Entity.update_all_entities_senses()

    event = execute_by_index(entity, "Pick Up", 0)
    assert event is not None
    assert entity.inventory.has_item(item.uuid) is True
    assert grid.get_object_position(item.uuid) is None


# =========================================================================
# Test 10: AttackObjectAction via get_available_actions
# =========================================================================
def test_attack_object_available_actions():
    create_test_grid()
    create_breakable_item(position=(4, 3), name="Crate", hp=20)
    entity = create_test_entity(position=(3, 3))
    Entity.update_all_entities_senses()

    available = entity.get_available_actions()
    attack_obj = [a for a in available.object_actions if a.template_name == "Attack Object"]
    assert len(attack_obj) == 1, f"Expected 1 Attack Object action, got {len(attack_obj)}"
    assert attack_obj[0].valid_targets[0].target_name == "Crate"


def test_attack_object_execute():
    create_test_grid()
    crate = create_breakable_item(position=(4, 3), name="Crate", hp=20)
    entity = create_test_entity(position=(3, 3))
    Entity.update_all_entities_senses()

    initial_hp = crate.get_hp()
    event = execute_by_index(entity, "Attack Object", 0)
    assert event is not None
    # Should have dealt some damage (auto-hit)
    assert crate.get_hp() < initial_hp or crate.get_hp() <= 0


def test_attack_object_destruction():
    """Attack until 0 HP — object destroyed and removed from grid/senses."""
    grid = create_test_grid()
    crate = create_breakable_item(position=(4, 3), name="Crate", hp=8)
    crate_uuid = crate.uuid
    entity = create_test_entity(position=(3, 3))
    Entity.update_all_entities_senses()

    # Deal enough damage to destroy
    crate.receive_damage(100, DamageType.BLUDGEONING, entity.uuid)
    assert grid.get_object_position(crate_uuid) is None
    assert BaseBlock.get(crate_uuid) is None


# =========================================================================
# Test 11: Non-pickable items don't appear as Pick Up targets
# =========================================================================
def test_non_pickable_not_in_pickup():
    create_test_grid()
    # Non-pickable item
    create_simple_item(position=(4, 3), name="Wall Fixture", pickable=False)
    entity = create_test_entity(position=(3, 3))
    Entity.update_all_entities_senses()

    available = entity.get_available_actions()
    pickup_actions = [a for a in available.object_actions if a.template_name == "Pick Up"]
    # Should have no valid targets (the wall fixture is not pickable)
    has_wall = False
    for pa in pickup_actions:
        for t in pa.valid_targets:
            if t.target_name == "Wall Fixture":
                has_wall = True
    assert not has_wall, "Non-pickable item should not appear as Pick Up target"


# =========================================================================
# Test 12: Item not in reach is not targetable
# =========================================================================
def test_item_out_of_reach():
    create_test_grid()
    # Item far away (more than 5ft)
    create_simple_item(position=(8, 8), name="Far Away Gem")
    entity = create_test_entity(position=(3, 3))
    Entity.update_all_entities_senses()

    available = entity.get_available_actions()
    pickup_actions = [a for a in available.object_actions if a.template_name == "Pick Up"]
    # No valid targets because too far
    for pa in pickup_actions:
        for t in pa.valid_targets:
            assert t.target_name != "Far Away Gem", "Out-of-reach item should not be Pick Up target"


# =========================================================================
# Test 13: get_objects_with_conditions (for environment step)
# =========================================================================
def test_objects_with_conditions():
    grid = create_test_grid()
    item = BaseItem(
        source_entity_uuid=uuid4(),
        name="Burning Item",
        allow_events_conditions=True,
    )
    grid.place_object(item.uuid, (5, 5))

    # No conditions yet
    assert len(grid.get_objects_with_conditions()) == 0

    # Add a condition
    cond = BaseCondition(
        name="Burning",
        source_entity_uuid=uuid4(),
        target_entity_uuid=item.uuid,
    )
    cond.duration.duration_type = DurationType.ROUNDS
    cond.duration.duration = 2
    item.add_condition(cond)

    assert len(grid.get_objects_with_conditions()) == 1

    # Advance duration
    item.advance_duration("Burning")
    assert "Burning" in item.active_conditions  # Still active (1 round left)

    item.advance_duration("Burning")
    assert "Burning" not in item.active_conditions  # Expired


# =========================================================================
# Test 14: No circular imports
# =========================================================================
def test_no_circular_imports():
    """Verify the dependency chain has no cycles."""
    # These should all import without error (if circular, they'd fail)
    from dnd.blocks.base_item import BaseItem as _BI  # type: ignore[reportUnusedImport]
    from dnd.blocks.inventory import Inventory as _Inv  # type: ignore[reportUnusedImport]
    from dnd.entity import Entity as _E  # type: ignore[reportUnusedImport]
    from dnd.actions import PickUp as _PU, AttackObject as _AO  # type: ignore[reportUnusedImport]
    from dnd.actions_functional import setup_standard_actions as _SSA  # type: ignore[reportUnusedImport]


# =========================================================================
# Main
# =========================================================================
if __name__ == "__main__":
    print("=" * 60)
    print("Items Phase 1 Integration Tests")
    print("=" * 60)

    print("\n--- BaseItem ---")
    run_test("BaseItem fields and spatial", test_base_item_fields)
    run_test("EquippableItem/UsableItem stubs", test_equippable_usable_stubs)

    print("\n--- Health/Damage ---")
    run_test("Item health damage", test_item_health_damage)
    run_test("Item health resistances", test_item_health_resistances)
    run_test("Item destruction", test_item_destruction)

    print("\n--- GridMap Objects ---")
    run_test("GridMap place/remove", test_gridmap_place_remove)
    run_test("GridMap clear", test_gridmap_clear)
    run_test("Blocking object walkability", test_blocking_object_walkability)
    run_test("Blocking object vision", test_blocking_object_vision)

    print("\n--- Senses ---")
    run_test("Senses discovers objects", test_senses_objects)
    run_test("Senses objects removed", test_senses_objects_removed)

    print("\n--- Inventory ---")
    run_test("Inventory add/remove", test_inventory_add_remove)
    run_test("Inventory capacity", test_inventory_capacity)
    run_test("Inventory transfer", test_inventory_transfer)
    run_test("Inventory find", test_inventory_find)

    print("\n--- Entity Loot/Drop ---")
    run_test("Entity loot item", test_entity_loot_item)
    run_test("Entity drop item", test_entity_drop_item)
    run_test("Lifecycle hooks", test_lifecycle_hooks)

    print("\n--- Actions ---")
    run_test("PickUp available actions", test_pickup_available_actions)
    run_test("PickUp execute", test_pickup_execute)
    run_test("AttackObject available actions", test_attack_object_available_actions)
    run_test("AttackObject execute", test_attack_object_execute)
    run_test("AttackObject destruction", test_attack_object_destruction)
    run_test("Non-pickable not in PickUp", test_non_pickable_not_in_pickup)
    run_test("Item out of reach", test_item_out_of_reach)

    print("\n--- Environment/Conditions ---")
    run_test("Objects with conditions", test_objects_with_conditions)

    print("\n--- Import Integrity ---")
    run_test("No circular imports", test_no_circular_imports)

    print("\n" + "=" * 60)
    print(f"Results: {tests_passed} passed, {tests_failed} failed")
    print("=" * 60)
    sys.exit(1 if tests_failed > 0 else 0)
