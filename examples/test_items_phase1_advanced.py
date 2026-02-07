"""
Items System Phase 1 Advanced Tests

Edge cases: vision blocking/unblocking, inventory isolation from grid,
drop action, multi-item scenarios, targeting constraints, cross-entity
interactions, conditions on destruction, and more.
"""

import sys
import traceback
from uuid import uuid4

from dnd.utils import reset_combat_state
from dnd.core.gridmap import get_map
from dnd.core.base_block import BaseBlock
from dnd.core.modifiers import DamageType
from dnd.core.base_conditions import BaseCondition, DurationType
from dnd.blocks.base_item import BaseItem, EquippableItem, ItemRarity
from dnd.blocks.inventory import Inventory
from dnd.blocks.health import Health, HealthConfig, HitDiceConfig
from dnd.entity import Entity, EntityConfig
from dnd.blocks.abilities import AbilityScoresConfig, AbilityConfig
from dnd.blocks.equipment import EquipmentConfig, WeaponSlot
from dnd.blocks.action_economy import ActionEconomyConfig
from dnd.actions_functional import setup_standard_actions, execute_by_index, execute_drop
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
    sword = create_longsword(entity.uuid)
    entity.equipment.equip(sword, WeaponSlot.MELEE_MAIN)
    setup_standard_actions(entity)
    return entity


def create_test_grid(width=10, height=10):
    """Create a simple floor grid."""
    grid = get_map()
    grid.create_rectangle(0, 0, width, height)
    return grid


def create_simple_item(position=None, name="Potion", pickable=True, weight=1.0):
    """Create a simple pickable item."""
    item = BaseItem(
        source_entity_uuid=uuid4(),
        name=name,
        is_pickable=pickable,
        weight=weight,
        value=50,
    )
    if position is not None:
        get_map().place_object(item.uuid, position)
    return item


def create_breakable_item(position=None, name="Crate", hp=20, blocks_vision=False, blocks_movement=False):
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
        blocks_vision_field=blocks_vision,
        blocks_movement=blocks_movement,
    )
    if position is not None:
        get_map().place_object(item.uuid, position)
    return item


def create_vision_blocker(position, name="Barricade", hp=20):
    """Create a breakable item that blocks vision."""
    return create_breakable_item(
        position=position, name=name, hp=hp,
        blocks_vision=True, blocks_movement=True,
    )


# =========================================================================
# Vision / LOS tests
# =========================================================================

def test_vision_blocked_by_object():
    """Entity can't see items/entities behind a vision-blocking object."""
    create_test_grid(20, 20)

    entity = create_test_entity(position=(1, 5))
    # Place a vision-blocking barricade between entity and far item
    create_vision_blocker(position=(3, 5))
    far_item = create_simple_item(position=(5, 5), name="Hidden Gem")

    Entity.update_all_entities_senses()

    # Entity should NOT see the item behind the barricade
    assert far_item.uuid not in entity.senses.objects, \
        "Should not see item behind vision-blocking object"


def test_destroy_vision_blocker_reveals_items():
    """Destroying a vision-blocking object reveals what's behind it."""
    create_test_grid(20, 20)

    entity = create_test_entity(position=(1, 5))
    barricade = create_vision_blocker(position=(3, 5), hp=8)
    far_item = create_simple_item(position=(5, 5), name="Hidden Gem")

    Entity.update_all_entities_senses()
    assert far_item.uuid not in entity.senses.objects

    # Destroy the barricade
    barricade.receive_damage(100, DamageType.BLUDGEONING, entity.uuid)
    assert BaseBlock.get(barricade.uuid) is None  # Destroyed

    # Update senses - now the gem should be visible
    Entity.update_all_entities_senses()
    assert far_item.uuid in entity.senses.objects, \
        "Should see item after vision blocker destroyed"


def test_destroy_vision_blocker_reveals_entity():
    """Destroying a vision-blocking object lets you see an entity behind it."""
    create_test_grid(20, 20)

    hero = create_test_entity(position=(1, 5), name="Hero")
    create_vision_blocker(position=(3, 5), hp=8)
    enemy = create_test_entity(position=(5, 5), name="Enemy", faction="monsters")

    Entity.update_all_entities_senses()
    assert enemy.uuid not in hero.senses.entities, \
        "Should not see enemy behind barricade"

    # Destroy the barricade via direct damage
    barricade_uuid = None
    for obj_uuid in hero.senses.objects:
        block = BaseBlock.get(obj_uuid)
        if block and block.name == "Barricade":
            barricade_uuid = obj_uuid
            break
    assert barricade_uuid is not None
    barricade = BaseBlock.get(barricade_uuid)
    assert isinstance(barricade, BaseItem)
    barricade.receive_damage(100, DamageType.BLUDGEONING, hero.uuid)

    Entity.update_all_entities_senses()
    assert enemy.uuid in hero.senses.entities, \
        "Should see enemy after vision blocker destroyed"


def test_drop_vision_blocking_item_blocks_los():
    """Dropping a vision-blocking item creates LOS block at entity position."""
    create_test_grid(20, 20)

    entity = create_test_entity(position=(3, 5), name="Dropper")
    far_entity = create_test_entity(position=(1, 5), name="Watcher", faction="monsters")

    # Create a vision-blocking item in entity's inventory
    blocker = BaseItem(
        source_entity_uuid=entity.uuid,
        name="Portable Wall",
        blocks_vision_field=True,
        blocks_movement=True,
        is_pickable=True,
    )
    entity.inventory.add_item(blocker)

    # Far item behind the drop position
    far_item = create_simple_item(position=(5, 5), name="Far Gem")

    Entity.update_all_entities_senses()
    # Watcher at (1,5) can see far_item at (5,5) - no obstacle
    assert far_item.uuid in far_entity.senses.objects, \
        "Watcher should see far item before drop"

    # Drop the blocker - it goes to entity's position (3,5)
    execute_drop(entity, blocker.uuid)

    Entity.update_all_entities_senses()
    # Now watcher at (1,5) should NOT see far_item at (5,5) - blocked by (3,5)
    assert far_item.uuid not in far_entity.senses.objects, \
        "Watcher should not see far item after vision blocker dropped"


def test_pickup_vision_blocker_unblocks_los():
    """Picking up a vision-blocking item from the ground restores LOS."""
    create_test_grid(20, 20)

    watcher = create_test_entity(position=(1, 5), name="Watcher")
    # Vision blocker at (3,5) - pickable this time
    blocker = BaseItem(
        source_entity_uuid=uuid4(),
        name="Portable Wall",
        blocks_vision_field=True,
        is_pickable=True,
    )
    get_map().place_object(blocker.uuid, (3, 5))
    far_item = create_simple_item(position=(5, 5), name="Far Gem")

    Entity.update_all_entities_senses()
    assert far_item.uuid not in watcher.senses.objects, \
        "Should not see far item through vision blocker"

    # An entity adjacent to the blocker picks it up
    picker = create_test_entity(position=(3, 4), name="Picker", faction="helpers")
    Entity.update_all_entities_senses()
    picker.loot_item(blocker)

    Entity.update_all_entities_senses()
    assert far_item.uuid in watcher.senses.objects, \
        "Should see far item after vision blocker picked up"


def test_movement_blocked_by_object():
    """A movement-blocking object prevents pathing through its cell."""
    create_test_grid(20, 20)
    grid = get_map()

    boulder = BaseItem(
        source_entity_uuid=uuid4(),
        name="Boulder",
        blocks_movement=True,
    )
    grid.place_object(boulder.uuid, (3, 5))

    entity = create_test_entity(position=(2, 5))
    Entity.update_all_entities_senses()

    # (3,5) should not be in walkable paths
    assert (3, 5) not in entity.senses.paths, \
        "Should not have path through movement-blocking object"


def test_destroy_movement_blocker_opens_path():
    """Destroying a movement-blocking object opens the path."""
    create_test_grid(20, 20)

    blocker = create_breakable_item(
        position=(3, 5), name="Wooden Gate", hp=8,
        blocks_movement=True,
    )
    entity = create_test_entity(position=(2, 5))
    Entity.update_all_entities_senses()

    assert (3, 5) not in entity.senses.paths

    blocker.receive_damage(100, DamageType.BLUDGEONING, entity.uuid)

    Entity.update_all_entities_senses()
    assert (3, 5) in entity.senses.paths, \
        "Should have path after movement blocker destroyed"


# =========================================================================
# Inventory isolation (items in bags are not on the ground)
# =========================================================================

def test_looted_item_not_on_ground():
    """An item in inventory has no grid position."""
    grid = create_test_grid()
    item = create_simple_item(position=(4, 3))
    entity = create_test_entity(position=(3, 3))
    Entity.update_all_entities_senses()

    entity.loot_item(item)
    assert grid.get_object_position(item.uuid) is None, \
        "Looted item should have no grid position"
    assert item.uuid not in grid.get_objects_at((4, 3)), \
        "Looted item should not be at its old grid position"


def test_looted_item_not_in_senses():
    """An item in inventory should not appear in any entity's senses.objects."""
    create_test_grid()
    item = create_simple_item(position=(4, 3))
    entity = create_test_entity(position=(3, 3))
    Entity.update_all_entities_senses()

    assert item.uuid in entity.senses.objects
    entity.loot_item(item)
    Entity.update_all_entities_senses()

    assert item.uuid not in entity.senses.objects, \
        "Looted item should not appear in senses.objects"


def test_inventory_item_not_targetable_by_attack_object():
    """A breakable item in inventory should not appear as AttackObject target."""
    create_test_grid()
    source_id = uuid4()
    crate = BaseItem(
        source_entity_uuid=source_id,
        name="Crate",
        is_pickable=True,
        is_targetable=True,
        health=BaseItem.create_item_health(source_id, 16),
    )
    # Put it in inventory, not on ground
    entity = create_test_entity(position=(3, 3))
    entity.inventory.add_item(crate)
    Entity.update_all_entities_senses()

    available = entity.get_available_actions()
    attack_obj = [a for a in available.object_actions if a.template_name == "Attack Object"]
    for action_info in attack_obj:
        for t in action_info.valid_targets:
            assert t.target_uuid != crate.uuid, \
                "Inventory item should not be an AttackObject target"


def test_inventory_item_not_targetable_by_pickup():
    """An item already in inventory should not appear as PickUp target."""
    create_test_grid()
    item = create_simple_item()
    entity = create_test_entity(position=(3, 3))
    entity.inventory.add_item(item)
    Entity.update_all_entities_senses()

    available = entity.get_available_actions()
    pickup_actions = [a for a in available.object_actions if a.template_name == "Pick Up"]
    for action_info in pickup_actions:
        for t in action_info.valid_targets:
            assert t.target_uuid != item.uuid, \
                "Inventory item should not be a PickUp target"


# =========================================================================
# Drop action
# =========================================================================

def test_drop_action_works():
    """Drop action places item from inventory onto ground at entity position."""
    grid = create_test_grid()
    entity = create_test_entity(position=(5, 5))
    item = create_simple_item(name="Gem", weight=0.5)
    entity.inventory.add_item(item)

    assert entity.inventory.has_item(item.uuid)
    event = execute_drop(entity, item.uuid)

    assert event is not None
    assert not entity.inventory.has_item(item.uuid), "Item should be removed from inventory"
    assert grid.get_object_position(item.uuid) == (5, 5), "Item should be on ground at entity pos"


def test_drop_action_not_in_available_actions():
    """Drop should never appear in get_available_actions."""
    create_test_grid()
    entity = create_test_entity(position=(5, 5))
    item = create_simple_item(name="Gem")
    entity.inventory.add_item(item)
    Entity.update_all_entities_senses()

    available = entity.get_available_actions()
    all_names = [a.template_name for a in available.all_actions]
    assert "Drop" not in all_names, \
        "Drop should not appear in available actions"


def test_drop_fires_on_drop_hook():
    """Drop action triggers the _on_drop lifecycle hook."""
    class HookItem(BaseItem):
        dropped: bool = False
        def _on_drop(self):
            self.dropped = True

    create_test_grid()
    entity = create_test_entity(position=(5, 5))
    item = HookItem(source_entity_uuid=uuid4(), name="Trackable")
    entity.inventory.add_item(item)

    execute_drop(entity, item.uuid)
    assert item.dropped is True, "_on_drop hook should fire"


def test_drop_invalid_item_uuid():
    """Dropping an item not in inventory should fail gracefully."""
    create_test_grid()
    entity = create_test_entity(position=(5, 5))
    fake_uuid = uuid4()

    event = execute_drop(entity, fake_uuid)
    # Should be cancelled (not crash)
    assert event is not None  # event returned but cancelled


def test_dropped_item_visible_to_nearby_entity():
    """After dropping an item, nearby entities can see it."""
    create_test_grid()
    dropper = create_test_entity(position=(5, 5), name="Dropper")
    watcher = create_test_entity(position=(5, 6), name="Watcher", faction="others")
    item = create_simple_item(name="Shiny Gem")
    dropper.inventory.add_item(item)
    Entity.update_all_entities_senses()

    # Watcher should NOT see the item (it's in dropper's inventory)
    assert item.uuid not in watcher.senses.objects

    execute_drop(dropper, item.uuid)
    Entity.update_all_entities_senses()

    # Now watcher should see it on the ground at (5,5)
    assert item.uuid in watcher.senses.objects, \
        "Watcher should see dropped item"
    assert watcher.senses.objects[item.uuid] == (5, 5)


def test_drop_multiple_items_same_position():
    """Multiple items can be dropped at the same position."""
    grid = create_test_grid()
    entity = create_test_entity(position=(5, 5))
    item1 = create_simple_item(name="Gem1")
    item2 = create_simple_item(name="Gem2")
    entity.inventory.add_item(item1)
    entity.inventory.add_item(item2)

    execute_drop(entity, item1.uuid)
    execute_drop(entity, item2.uuid)

    objects_at = grid.get_objects_at((5, 5))
    assert item1.uuid in objects_at
    assert item2.uuid in objects_at


# =========================================================================
# Multi-item and cross-entity scenarios
# =========================================================================

def test_multiple_items_at_same_position():
    """Multiple items at the same position all appear in senses.objects."""
    create_test_grid()
    item1 = create_simple_item(position=(4, 3), name="Gem1")
    item2 = create_simple_item(position=(4, 3), name="Gem2")
    entity = create_test_entity(position=(3, 3))
    Entity.update_all_entities_senses()

    assert item1.uuid in entity.senses.objects
    assert item2.uuid in entity.senses.objects


def test_pickup_one_of_multiple_items_leaves_others():
    """Picking up one item from a stack leaves others on the ground."""
    grid = create_test_grid()
    item1 = create_simple_item(position=(4, 3), name="Gem1")
    item2 = create_simple_item(position=(4, 3), name="Gem2")
    entity = create_test_entity(position=(3, 3))
    Entity.update_all_entities_senses()

    entity.loot_item(item1)
    assert grid.get_object_position(item1.uuid) is None
    assert grid.get_object_position(item2.uuid) == (4, 3), \
        "Second item should still be on the ground"
    assert item2.uuid in grid.get_objects_at((4, 3))


def test_two_entities_see_same_item():
    """Two entities can both see the same floor item."""
    create_test_grid()
    item = create_simple_item(position=(5, 5), name="Shared Gem")
    e1 = create_test_entity(position=(4, 5), name="Entity1")
    e2 = create_test_entity(position=(6, 5), name="Entity2", faction="others")
    Entity.update_all_entities_senses()

    assert item.uuid in e1.senses.objects
    assert item.uuid in e2.senses.objects


def test_one_entity_picks_up_other_loses_visibility():
    """When one entity picks up an item, other entity no longer sees it on the ground."""
    create_test_grid()
    item = create_simple_item(position=(5, 5), name="Shared Gem")
    e1 = create_test_entity(position=(5, 4), name="Picker")
    e2 = create_test_entity(position=(5, 6), name="Watcher", faction="others")
    Entity.update_all_entities_senses()

    assert item.uuid in e2.senses.objects
    e1.loot_item(item)
    Entity.update_all_entities_senses()

    assert item.uuid not in e2.senses.objects, \
        "Watcher should no longer see picked-up item"


def test_transfer_between_entity_inventories():
    """Transfer item between two entity inventories."""
    create_test_grid()
    e1 = create_test_entity(position=(3, 3), name="Giver")
    e2 = create_test_entity(position=(4, 3), name="Receiver", faction="others")
    item = create_simple_item(name="Gift")
    e1.inventory.add_item(item)

    result = e1.inventory.transfer_to(item.uuid, e2.inventory)
    assert result is True
    assert not e1.inventory.has_item(item.uuid)
    assert e2.inventory.has_item(item.uuid)


# =========================================================================
# Targeting edge cases
# =========================================================================

def test_non_breakable_item_not_attack_target():
    """A targetable item with no health (non-breakable) can't be attacked."""
    create_test_grid()
    item = BaseItem(
        source_entity_uuid=uuid4(),
        name="Indestructible Pillar",
        is_targetable=True,
        is_pickable=False,
        health=None,  # Not breakable
    )
    get_map().place_object(item.uuid, (4, 3))
    entity = create_test_entity(position=(3, 3))
    Entity.update_all_entities_senses()

    available = entity.get_available_actions()
    attack_obj = [a for a in available.object_actions if a.template_name == "Attack Object"]
    for action_info in attack_obj:
        for t in action_info.valid_targets:
            assert t.target_uuid != item.uuid, \
                "Non-breakable item should not be an Attack Object target"


def test_item_not_visible_not_targetable():
    """An item behind a wall is not in senses.objects and not targetable."""
    grid = create_test_grid(20, 20)
    # Create a wall column at x=3 blocking vision
    for y in range(0, 10):
        grid.set_tile(3, y, walkable=False, visible=False, name="Wall")

    item = create_simple_item(position=(5, 5), name="Hidden Gem")
    entity = create_test_entity(position=(1, 5))
    Entity.update_all_entities_senses()

    assert item.uuid not in entity.senses.objects, \
        "Item behind wall should not be visible"

    available = entity.get_available_actions()
    pickup_actions = [a for a in available.object_actions if a.template_name == "Pick Up"]
    for action_info in pickup_actions:
        for t in action_info.valid_targets:
            assert t.target_uuid != item.uuid, \
                "Item behind wall should not be a PickUp target"


def test_pickup_full_inventory_fails():
    """PickUp action fails when inventory is full."""
    create_test_grid()
    entity = create_test_entity(position=(3, 3))
    # Set max_slots to 1
    entity.inventory.max_slots = 1
    existing = create_simple_item(name="Filler")
    entity.inventory.add_item(existing)

    floor_item = create_simple_item(position=(4, 3), name="Extra Item")
    Entity.update_all_entities_senses()

    # Should not appear as valid target since inventory is full
    available = entity.get_available_actions()
    pickup_actions = [a for a in available.object_actions if a.template_name == "Pick Up"]
    for action_info in pickup_actions:
        for t in action_info.valid_targets:
            assert t.target_uuid != floor_item.uuid, \
                "Should not be able to pick up with full inventory"


def test_pickup_at_exactly_5ft():
    """Item at exactly 5ft (1 tile diagonal) is reachable."""
    create_test_grid()
    item = create_simple_item(position=(4, 4), name="Close Gem")
    entity = create_test_entity(position=(3, 3))
    Entity.update_all_entities_senses()

    available = entity.get_available_actions()
    pickup_actions = [a for a in available.object_actions if a.template_name == "Pick Up"]
    found = False
    for action_info in pickup_actions:
        for t in action_info.valid_targets:
            if t.target_uuid == item.uuid:
                found = True
    assert found, "Item at 5ft (diagonal) should be reachable"


def test_pickup_at_10ft_fails():
    """Item at 10ft (2 tiles away) is NOT reachable."""
    create_test_grid()
    item = create_simple_item(position=(5, 3), name="Too Far Gem")
    entity = create_test_entity(position=(3, 3))
    Entity.update_all_entities_senses()

    available = entity.get_available_actions()
    pickup_actions = [a for a in available.object_actions if a.template_name == "Pick Up"]
    for action_info in pickup_actions:
        for t in action_info.valid_targets:
            assert t.target_uuid != item.uuid, \
                "Item at 10ft should NOT be reachable for PickUp"


# =========================================================================
# Condition / destruction edge cases
# =========================================================================

def test_destroy_item_with_conditions_cleans_up():
    """Destroying an item with active conditions cleans them up."""
    create_test_grid()
    item = BaseItem(
        source_entity_uuid=uuid4(),
        name="Burning Crate",
        is_targetable=True,
        health=BaseItem.create_item_health(uuid4(), 8),
        allow_events_conditions=True,
    )
    get_map().place_object(item.uuid, (5, 5))

    cond = BaseCondition(
        name="OnFire",
        source_entity_uuid=uuid4(),
        target_entity_uuid=item.uuid,
    )
    cond.duration.duration_type = DurationType.ROUNDS
    cond.duration.duration = 5
    item.add_condition(cond)
    assert "OnFire" in item.active_conditions

    item.receive_damage(100, DamageType.FIRE, uuid4())
    # Item destroyed - conditions should be cleaned up
    assert BaseBlock.get(item.uuid) is None


def test_destroy_all_items_at_position():
    """Destroying all items at a position leaves the position clear."""
    grid = create_test_grid()
    c1 = create_breakable_item(position=(5, 5), name="Crate1", hp=8)
    c2 = create_breakable_item(position=(5, 5), name="Crate2", hp=8)

    assert len(grid.get_objects_at((5, 5))) == 2

    c1.receive_damage(100, DamageType.BLUDGEONING, uuid4())
    c2.receive_damage(100, DamageType.BLUDGEONING, uuid4())

    assert len(grid.get_objects_at((5, 5))) == 0, \
        "All items should be removed after destruction"


def test_item_zero_weight_in_inventory():
    """Items with 0 weight can be added to inventory."""
    inv = Inventory(source_entity_uuid=uuid4(), weight_capacity=5.0)
    item = BaseItem(source_entity_uuid=uuid4(), name="Feather", weight=0.0)

    assert inv.can_add(item) is True
    assert inv.add_item(item) is True
    assert inv.total_weight == 0.0
    assert inv.item_count == 1


def test_stack_count_affects_weight():
    """Stack count multiplies weight for inventory purposes."""
    inv = Inventory(source_entity_uuid=uuid4(), weight_capacity=10.0)
    item = BaseItem(source_entity_uuid=uuid4(), name="Arrow", weight=0.5, stack_count=5)

    assert inv.can_add(item) is True
    inv.add_item(item)
    assert inv.total_weight == 2.5  # 0.5 * 5

    heavy_stack = BaseItem(source_entity_uuid=uuid4(), name="Cannonball", weight=5.0, stack_count=3)
    assert inv.can_add(heavy_stack) is False  # 2.5 + 15.0 > 10.0


def test_loot_multiple_items_sequentially():
    """Entity can loot multiple items in sequence."""
    create_test_grid()
    entity = create_test_entity(position=(3, 3))
    items = []
    for i in range(5):
        item = create_simple_item(position=(4, 3), name=f"Gem_{i}")
        items.append(item)
    Entity.update_all_entities_senses()

    for item in items:
        result = entity.loot_item(item)
        assert result is True

    assert entity.inventory.item_count == 5
    for item in items:
        assert entity.inventory.has_item(item.uuid)


def test_loot_and_drop_round_trip():
    """Loot then drop returns item to the ground at entity position."""
    grid = create_test_grid()
    item = create_simple_item(position=(4, 3), name="Gem")
    entity = create_test_entity(position=(3, 3))
    Entity.update_all_entities_senses()

    # Loot from (4,3)
    entity.loot_item(item)
    assert grid.get_object_position(item.uuid) is None

    # Drop at entity position (3,3)
    entity.drop_item(item.uuid)
    assert grid.get_object_position(item.uuid) == (3, 3), \
        "Dropped item should be at entity position, not original position"


def test_place_object_then_place_another_at_same_position():
    """Both objects tracked when placed at the same position."""
    grid = create_test_grid()
    item1 = BaseItem(source_entity_uuid=uuid4(), name="A")
    item2 = BaseItem(source_entity_uuid=uuid4(), name="B")

    grid.place_object(item1.uuid, (5, 5))
    grid.place_object(item2.uuid, (5, 5))

    objects = grid.get_objects_at((5, 5))
    assert item1.uuid in objects
    assert item2.uuid in objects
    assert grid.get_object_position(item1.uuid) == (5, 5)
    assert grid.get_object_position(item2.uuid) == (5, 5)


def test_equippable_item_flags():
    """EquippableItem has correct type flags."""
    eq = EquippableItem(source_entity_uuid=uuid4(), name="Magic Ring", rarity=ItemRarity.RARE)
    assert eq.is_equippable is True
    assert eq.is_pickable is True
    assert eq.is_usable is False
    assert eq.rarity == ItemRarity.RARE


def test_item_tags_filtering():
    """Items with tags can be filtered across inventory."""
    inv = Inventory(source_entity_uuid=uuid4())
    potion1 = BaseItem(source_entity_uuid=uuid4(), name="Health Potion", tags=["consumable", "healing"])
    potion2 = BaseItem(source_entity_uuid=uuid4(), name="Mana Potion", tags=["consumable", "magic"])
    sword = BaseItem(source_entity_uuid=uuid4(), name="Sword", tags=["weapon", "melee"])
    shield = BaseItem(source_entity_uuid=uuid4(), name="Shield", tags=["armor", "shield"])

    for item in [potion1, potion2, sword, shield]:
        inv.add_item(item)

    assert len(inv.find_items_by_tag("consumable")) == 2
    assert len(inv.find_items_by_tag("weapon")) == 1
    assert len(inv.find_items_by_tag("healing")) == 1
    assert len(inv.find_items_by_tag("nonexistent")) == 0


# =========================================================================
# Main
# =========================================================================
if __name__ == "__main__":
    print("=" * 60)
    print("Items Phase 1 Advanced Tests")
    print("=" * 60)

    print("\n--- Vision / LOS ---")
    run_test("Vision blocked by object", test_vision_blocked_by_object)
    run_test("Destroy vision blocker reveals items", test_destroy_vision_blocker_reveals_items)
    run_test("Destroy vision blocker reveals entity", test_destroy_vision_blocker_reveals_entity)
    run_test("Drop vision-blocking item blocks LOS", test_drop_vision_blocking_item_blocks_los)
    run_test("Pick up vision blocker unblocks LOS", test_pickup_vision_blocker_unblocks_los)
    run_test("Movement blocked by object", test_movement_blocked_by_object)
    run_test("Destroy movement blocker opens path", test_destroy_movement_blocker_opens_path)

    print("\n--- Inventory Isolation ---")
    run_test("Looted item not on ground", test_looted_item_not_on_ground)
    run_test("Looted item not in senses", test_looted_item_not_in_senses)
    run_test("Inventory item not targetable by AttackObject", test_inventory_item_not_targetable_by_attack_object)
    run_test("Inventory item not targetable by PickUp", test_inventory_item_not_targetable_by_pickup)

    print("\n--- Drop Action ---")
    run_test("Drop action works", test_drop_action_works)
    run_test("Drop not in available actions", test_drop_action_not_in_available_actions)
    run_test("Drop fires _on_drop hook", test_drop_fires_on_drop_hook)
    run_test("Drop invalid item UUID", test_drop_invalid_item_uuid)
    run_test("Dropped item visible to nearby entity", test_dropped_item_visible_to_nearby_entity)
    run_test("Drop multiple items same position", test_drop_multiple_items_same_position)

    print("\n--- Multi-Item / Cross-Entity ---")
    run_test("Multiple items at same position", test_multiple_items_at_same_position)
    run_test("Pickup one leaves others", test_pickup_one_of_multiple_items_leaves_others)
    run_test("Two entities see same item", test_two_entities_see_same_item)
    run_test("One entity picks up, other loses visibility", test_one_entity_picks_up_other_loses_visibility)
    run_test("Transfer between entity inventories", test_transfer_between_entity_inventories)

    print("\n--- Targeting Edge Cases ---")
    run_test("Non-breakable item not attack target", test_non_breakable_item_not_attack_target)
    run_test("Item behind wall not visible/targetable", test_item_not_visible_not_targetable)
    run_test("PickUp full inventory fails", test_pickup_full_inventory_fails)
    run_test("Pickup at exactly 5ft", test_pickup_at_exactly_5ft)
    run_test("Pickup at 10ft fails", test_pickup_at_10ft_fails)

    print("\n--- Conditions / Destruction ---")
    run_test("Destroy item with conditions cleans up", test_destroy_item_with_conditions_cleans_up)
    run_test("Destroy all items at position", test_destroy_all_items_at_position)

    print("\n--- Inventory Operations ---")
    run_test("Zero weight item in inventory", test_item_zero_weight_in_inventory)
    run_test("Stack count affects weight", test_stack_count_affects_weight)
    run_test("Loot multiple items sequentially", test_loot_multiple_items_sequentially)
    run_test("Loot and drop round trip", test_loot_and_drop_round_trip)
    run_test("Place two objects at same position", test_place_object_then_place_another_at_same_position)
    run_test("EquippableItem flags", test_equippable_item_flags)
    run_test("Item tags filtering", test_item_tags_filtering)

    print("\n" + "=" * 60)
    print(f"Results: {tests_passed} passed, {tests_failed} failed")
    print("=" * 60)
    sys.exit(1 if tests_failed > 0 else 0)
