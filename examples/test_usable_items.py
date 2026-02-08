"""
UsableItem System Tests

Tests environment object discovery, charge system, and all test items:
Door (Approach A + B), Lever, Chest, Campfire.
"""

import sys
import traceback
from uuid import uuid4

from dnd.utils import reset_combat_state
from dnd.core.gridmap import get_map
from dnd.core.events import EventQueue
from dnd.blocks.base_item import BaseItem, UsableItem
from dnd.entity import Entity, EntityConfig
from dnd.blocks.abilities import AbilityScoresConfig, AbilityConfig
from dnd.blocks.equipment import EquipmentConfig
from dnd.blocks.action_economy import ActionEconomyConfig
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.actions_functional import setup_standard_actions, execute_use_action
from dnd.items.weapons import create_shortsword
from dnd.items.test_items import (
    TestDoorA, TestDoorB, InteractDoorAction,
    TrapLever, PullLeverAction,
    StorageChest, LootAllAction,
    RestAction, CookAction,
)
from dnd.tiles import create_spike_zone

tests_passed = 0
tests_failed = 0


def strip_item_suffix(template_name: str) -> str:
    """Strip __item_<uuid> suffix from template name for test assertions."""
    return template_name.split("__item_")[0] if "__item_" in template_name else template_name


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
        health=HealthConfig(hit_dices=[HitDiceConfig(
            hit_dice_value=10, hit_dice_count=5, mode="maximums")]),
        equipment=EquipmentConfig(),
        action_economy=ActionEconomyConfig(),
        proficiency_bonus=2,
        position=position,
        faction=faction,
    )
    entity = Entity.create(name=name, source_entity_uuid=source_id, config=config)
    setup_standard_actions(entity)
    return entity


def create_test_grid():
    """Create a simple 10x10 floor grid."""
    grid = get_map()
    grid.create_rectangle(0, 0, 10, 10)
    return grid


# =============================================================================
# Door Approach A Tests (override get_use_actions pattern)
# =============================================================================

def test_door_a_discovery():
    """Closed door surfaces 'Open Door', open door surfaces 'Close Door'."""
    grid = create_test_grid()
    entity = create_test_entity(position=(3, 3))

    # Place closed door at (4, 3) — adjacent to entity
    door = TestDoorA(source_entity_uuid=uuid4(), position=(4, 3))
    grid.place_object(door.uuid, (4, 3))
    Entity.update_all_entities_senses()

    # Closed door: should surface "Open Door"
    result = entity.get_available_actions()
    use_names = [strip_item_suffix(a.template_name) for a in result.self_actions if a.is_item_use]
    assert "Open Door" in use_names, f"Expected 'Open Door', got {use_names}"
    assert "Close Door" not in use_names, f"Should not have 'Close Door' when closed"

    # Open the door manually
    door.is_open = True
    door.blocks_movement = False
    door.blocks_vision_field = False

    # Open door: should surface "Close Door"
    result = entity.get_available_actions()
    use_names = [strip_item_suffix(a.template_name) for a in result.self_actions if a.is_item_use]
    assert "Close Door" in use_names, f"Expected 'Close Door', got {use_names}"
    assert "Open Door" not in use_names, f"Should not have 'Open Door' when open"


def test_door_a_open_close_cycle():
    """Execute open -> close -> verify full cycle."""
    grid = create_test_grid()
    entity = create_test_entity(position=(3, 3))

    door = TestDoorA(source_entity_uuid=uuid4(), position=(4, 3))
    grid.place_object(door.uuid, (4, 3))
    Entity.update_all_entities_senses()

    # Open the door
    assert not door.is_open
    event = execute_use_action(entity, door.uuid, "Open Door")
    assert event is not None
    assert not event.canceled
    assert door.is_open
    assert not door.blocks_movement
    assert not door.blocks_vision_field

    # Close the door
    event = execute_use_action(entity, door.uuid, "Close Door")
    assert event is not None
    assert not event.canceled
    assert not door.is_open
    assert door.blocks_movement
    assert door.blocks_vision_field


def test_door_a_blocks_movement():
    """Closed door blocks walkability, open allows."""
    grid = create_test_grid()
    entity = create_test_entity(position=(3, 3))

    door = TestDoorA(source_entity_uuid=uuid4(), position=(4, 3))
    grid.place_object(door.uuid, (4, 3))
    Entity.update_all_entities_senses()

    # Closed: blocks walking
    assert door.blocks_walking(), "Closed door should block walking"

    # Open it
    execute_use_action(entity, door.uuid, "Open Door")

    # Open: allows walking
    assert not door.blocks_walking(), "Open door should not block walking"


# =============================================================================
# Door Approach B Tests (default use_action_templates pattern)
# =============================================================================

def test_door_b_discovery():
    """Door always surfaces 'Interact Door' regardless of state."""
    grid = create_test_grid()
    entity = create_test_entity(position=(3, 3))

    door = TestDoorB(
        source_entity_uuid=uuid4(),
        position=(4, 3),
        use_action_templates=[InteractDoorAction(
            source_entity_uuid=uuid4(), template=True)],
    )
    grid.place_object(door.uuid, (4, 3))
    Entity.update_all_entities_senses()

    # Should always show "Interact Door"
    result = entity.get_available_actions()
    use_names = [strip_item_suffix(a.template_name) for a in result.self_actions if a.is_item_use]
    assert "Interact Door" in use_names, f"Expected 'Interact Door', got {use_names}"


def test_door_b_toggle():
    """Execute interact -> toggles state -> execute again -> toggles back."""
    grid = create_test_grid()
    entity = create_test_entity(position=(3, 3))

    door = TestDoorB(
        source_entity_uuid=uuid4(),
        position=(4, 3),
        use_action_templates=[InteractDoorAction(
            source_entity_uuid=uuid4(), template=True)],
    )
    grid.place_object(door.uuid, (4, 3))
    Entity.update_all_entities_senses()

    assert not door.is_open
    assert door.blocks_movement

    # Toggle open
    event = execute_use_action(entity, door.uuid, "Interact Door")
    assert event is not None
    assert not event.canceled
    assert door.is_open
    assert not door.blocks_movement

    # Toggle closed
    event = execute_use_action(entity, door.uuid, "Interact Door")
    assert event is not None
    assert not event.canceled
    assert not door.is_open
    assert door.blocks_movement


def test_door_b_uses_default_field():
    """Verify TestDoorB does not override get_use_actions (uses default)."""
    # Check that TestDoorB's get_use_actions is inherited from UsableItem
    assert TestDoorB.get_use_actions is UsableItem.get_use_actions, \
        "TestDoorB should use default get_use_actions from UsableItem"


# =============================================================================
# Door spatial effects (shared)
# =============================================================================

def test_door_vision_blocking():
    """Closed door blocks FOV, open allows."""
    grid = create_test_grid()
    entity = create_test_entity(position=(3, 3))

    # Place door between entity and target position
    door = TestDoorA(source_entity_uuid=uuid4(), position=(4, 3))
    grid.place_object(door.uuid, (4, 3))
    Entity.update_all_entities_senses()

    # Closed: should block vision through (4,3)
    assert door.blocks_vision(), "Closed door should block vision"

    # Open the door
    execute_use_action(entity, door.uuid, "Open Door")

    # Open: should not block vision
    assert not door.blocks_vision(), "Open door should not block vision"


# =============================================================================
# Lever Tests
# =============================================================================

def test_lever_discovery():
    """'Pull Lever' visible near lever."""
    grid = create_test_grid()
    entity = create_test_entity(position=(5, 5))

    spike_positions = {(3, 3), (3, 4)}
    _, spike_handler = create_spike_zone(spike_positions)

    lever = TrapLever(
        source_entity_uuid=uuid4(),
        position=(5, 6),
        charges=1,
        use_action_templates=[PullLeverAction(
            source_entity_uuid=uuid4(),
            trap_handler_uuid=spike_handler.uuid,
            template=True,
        )],
    )
    grid.place_object(lever.uuid, (5, 6))
    Entity.update_all_entities_senses()

    result = entity.get_available_actions()
    use_names = [strip_item_suffix(a.template_name) for a in result.self_actions if a.is_item_use]
    assert "Pull Lever" in use_names, f"Expected 'Pull Lever', got {use_names}"


def test_lever_deactivates_trap():
    """Pull lever -> remove_spatial_handler, verify handler gone."""
    grid = create_test_grid()
    entity = create_test_entity(position=(5, 5))

    spike_positions = {(3, 3), (3, 4)}
    _, spike_handler = create_spike_zone(spike_positions)

    # Verify handler is registered
    handlers_before = EventQueue.get_spatial_handlers_at((3, 3))
    assert len(handlers_before) > 0, "Spike handler should be registered"

    lever = TrapLever(
        source_entity_uuid=uuid4(),
        position=(5, 6),
        charges=1,
        use_action_templates=[PullLeverAction(
            source_entity_uuid=uuid4(),
            trap_handler_uuid=spike_handler.uuid,
            template=True,
        )],
    )
    grid.place_object(lever.uuid, (5, 6))
    Entity.update_all_entities_senses()

    # Pull lever
    event = execute_use_action(entity, lever.uuid, "Pull Lever")
    assert event is not None
    assert not event.canceled

    # Verify handler removed
    handlers_after = EventQueue.get_spatial_handlers_at((3, 3))
    assert len(handlers_after) == 0, "Spike handler should be removed after pulling lever"


def test_lever_one_use():
    """After pulling (charges=1->0), no action available."""
    grid = create_test_grid()
    entity = create_test_entity(position=(5, 5))

    spike_positions = {(3, 3)}
    _, spike_handler = create_spike_zone(spike_positions)

    lever = TrapLever(
        source_entity_uuid=uuid4(),
        position=(5, 6),
        charges=1,
        use_action_templates=[PullLeverAction(
            source_entity_uuid=uuid4(),
            trap_handler_uuid=spike_handler.uuid,
            template=True,
        )],
    )
    grid.place_object(lever.uuid, (5, 6))
    Entity.update_all_entities_senses()

    # Pull lever (consumes charge)
    execute_use_action(entity, lever.uuid, "Pull Lever")
    assert lever.charges == 0, f"Charges should be 0, got {lever.charges}"

    # No more actions available
    result = entity.get_available_actions()
    use_names = [strip_item_suffix(a.template_name) for a in result.self_actions if a.is_item_use]
    assert "Pull Lever" not in use_names, "Should not have 'Pull Lever' after charges depleted"


# =============================================================================
# Chest Tests
# =============================================================================

def test_chest_discovery():
    """'Loot All' visible when chest has items."""
    grid = create_test_grid()
    entity = create_test_entity(position=(5, 5))

    chest = StorageChest(
        source_entity_uuid=uuid4(),
        position=(6, 5),
        use_action_templates=[LootAllAction(
            source_entity_uuid=uuid4(), template=True)],
    )
    # Add items to chest
    sword = create_shortsword(uuid4())
    chest.chest_inventory.add_item(sword)
    grid.place_object(chest.uuid, (6, 5))
    Entity.update_all_entities_senses()

    result = entity.get_available_actions()
    use_names = [strip_item_suffix(a.template_name) for a in result.self_actions if a.is_item_use]
    assert "Loot All" in use_names, f"Expected 'Loot All', got {use_names}"


def test_chest_loot_transfers():
    """Items move from chest to entity inventory."""
    grid = create_test_grid()
    entity = create_test_entity(position=(5, 5))

    chest = StorageChest(
        source_entity_uuid=uuid4(),
        position=(6, 5),
        use_action_templates=[LootAllAction(
            source_entity_uuid=uuid4(), template=True)],
    )
    sword = create_shortsword(uuid4())
    potion = BaseItem(source_entity_uuid=uuid4(), name="Healing Potion")
    chest.chest_inventory.add_item(sword)
    chest.chest_inventory.add_item(potion)
    grid.place_object(chest.uuid, (6, 5))
    Entity.update_all_entities_senses()

    assert len(chest.chest_inventory.items) == 2
    initial_inv_count = len(entity.inventory.items)

    event = execute_use_action(entity, chest.uuid, "Loot All")
    assert event is not None
    assert not event.canceled

    # Items transferred
    assert len(chest.chest_inventory.items) == 0, "Chest should be empty"
    assert len(entity.inventory.items) == initial_inv_count + 2, \
        f"Entity should have 2 more items, got {len(entity.inventory.items)}"


def test_empty_chest_no_action():
    """After looting, no 'Loot All' (validate fails)."""
    grid = create_test_grid()
    entity = create_test_entity(position=(5, 5))

    chest = StorageChest(
        source_entity_uuid=uuid4(),
        position=(6, 5),
        use_action_templates=[LootAllAction(
            source_entity_uuid=uuid4(), template=True)],
    )
    sword = create_shortsword(uuid4())
    chest.chest_inventory.add_item(sword)
    grid.place_object(chest.uuid, (6, 5))
    Entity.update_all_entities_senses()

    # Loot everything
    execute_use_action(entity, chest.uuid, "Loot All")

    # Empty chest: action should not appear
    result = entity.get_available_actions()
    use_names = [strip_item_suffix(a.template_name) for a in result.self_actions if a.is_item_use]
    assert "Loot All" not in use_names, "Should not have 'Loot All' when chest is empty"


def test_chest_destroy_drops_loot():
    """Break chest -> items spill onto floor at chest position."""
    grid = create_test_grid()

    chest = StorageChest(
        source_entity_uuid=uuid4(),
        position=(6, 5),
        is_targetable=True,
        health=BaseItem.create_item_health(uuid4(), hp=8),
        use_action_templates=[LootAllAction(
            source_entity_uuid=uuid4(), template=True)],
    )
    sword = create_shortsword(uuid4())
    potion = BaseItem(source_entity_uuid=uuid4(), name="Healing Potion")
    chest.chest_inventory.add_item(sword)
    chest.chest_inventory.add_item(potion)
    grid.place_object(chest.uuid, (6, 5))
    Entity.update_all_entities_senses()

    sword_uuid = sword.uuid
    potion_uuid = potion.uuid

    # Destroy the chest
    chest.destroy()

    # Items should be on the floor at chest position
    objects_at = grid.get_objects_at((6, 5))
    # Chest itself is gone (destroyed removes from grid)
    assert sword_uuid in objects_at, "Sword should be on floor at chest position"
    assert potion_uuid in objects_at, "Potion should be on floor at chest position"


# =============================================================================
# Campfire Tests (multi-action item)
# =============================================================================

def test_campfire_multiple_actions():
    """Campfire surfaces both 'Rest' and 'Cook' actions."""
    grid = create_test_grid()
    entity = create_test_entity(position=(5, 5))

    campfire = UsableItem(
        source_entity_uuid=uuid4(),
        name="Campfire",
        is_pickable=False,
        position=(5, 6),
        use_action_templates=[
            RestAction(source_entity_uuid=uuid4(), template=True),
            CookAction(source_entity_uuid=uuid4(), template=True),
        ],
    )
    grid.place_object(campfire.uuid, (5, 6))
    Entity.update_all_entities_senses()

    result = entity.get_available_actions()
    use_names = [strip_item_suffix(a.template_name) for a in result.self_actions if a.is_item_use]
    assert "Rest" in use_names, f"Expected 'Rest', got {use_names}"
    assert "Cook" in use_names, f"Expected 'Cook', got {use_names}"


def test_campfire_execute_each():
    """Can execute each action independently."""
    grid = create_test_grid()
    entity = create_test_entity(position=(5, 5))

    campfire = UsableItem(
        source_entity_uuid=uuid4(),
        name="Campfire",
        is_pickable=False,
        position=(5, 6),
        use_action_templates=[
            RestAction(source_entity_uuid=uuid4(), template=True),
            CookAction(source_entity_uuid=uuid4(), template=True),
        ],
    )
    grid.place_object(campfire.uuid, (5, 6))
    Entity.update_all_entities_senses()

    # Damage entity first so heal has effect
    entity.health.add_damage(10)
    hp_before = entity.get_hp()

    # Rest — heals 1d6
    event = execute_use_action(entity, campfire.uuid, "Rest")
    assert event is not None
    assert not event.canceled
    hp_after_rest = entity.get_hp()
    assert hp_after_rest > hp_before, f"HP should increase from rest: {hp_before} -> {hp_after_rest}"

    # Cook — adds temp HP
    event = execute_use_action(entity, campfire.uuid, "Cook")
    assert event is not None
    assert not event.canceled
    temp_hp = entity.health.temporary_hit_points.score
    assert temp_hp > 0, f"Should have temp HP, got {temp_hp}"


# =============================================================================
# General Tests
# =============================================================================

def test_out_of_range():
    """Entity >5ft from object sees no use actions."""
    grid = create_test_grid()
    entity = create_test_entity(position=(0, 0))

    door = TestDoorA(source_entity_uuid=uuid4(), position=(8, 8))
    grid.place_object(door.uuid, (8, 8))
    Entity.update_all_entities_senses()

    result = entity.get_available_actions()
    use_names = [strip_item_suffix(a.template_name) for a in result.self_actions if a.is_item_use]
    assert len(use_names) == 0, f"Should have no use actions at range, got {use_names}"


def test_non_usable_ignored():
    """Regular BaseItem on floor generates no use actions."""
    grid = create_test_grid()
    entity = create_test_entity(position=(3, 3))

    item = BaseItem(source_entity_uuid=uuid4(), name="Rock", is_pickable=False)
    grid.place_object(item.uuid, (4, 3))
    Entity.update_all_entities_senses()

    result = entity.get_available_actions()
    use_names = [strip_item_suffix(a.template_name) for a in result.self_actions if a.is_item_use]
    assert len(use_names) == 0, f"Regular BaseItem should not generate use actions, got {use_names}"


def test_charges_system():
    """Verify charges decrement, depleted returns no actions."""
    grid = create_test_grid()
    entity = create_test_entity(position=(5, 5))

    # Item with 2 charges
    campfire = UsableItem(
        source_entity_uuid=uuid4(),
        name="Small Campfire",
        is_pickable=False,
        position=(5, 6),
        charges=2,
        max_charges=2,
        use_action_templates=[
            RestAction(source_entity_uuid=uuid4(), template=True),
        ],
    )
    grid.place_object(campfire.uuid, (5, 6))
    Entity.update_all_entities_senses()

    assert campfire.charges == 2

    # Use 1
    execute_use_action(entity, campfire.uuid, "Rest")
    assert campfire.charges == 1, f"Expected 1 charge, got {campfire.charges}"

    # Still available
    result = entity.get_available_actions()
    use_names = [strip_item_suffix(a.template_name) for a in result.self_actions if a.is_item_use]
    assert "Rest" in use_names, "Should still have 'Rest' with 1 charge"

    # Use 2
    execute_use_action(entity, campfire.uuid, "Rest")
    assert campfire.charges == 0, f"Expected 0 charges, got {campfire.charges}"

    # Depleted — no more actions
    result = entity.get_available_actions()
    use_names = [strip_item_suffix(a.template_name) for a in result.self_actions if a.is_item_use]
    assert "Rest" not in use_names, "Should not have 'Rest' when charges depleted"


# =============================================================================
# Main
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("UsableItem System Tests")
    print("=" * 60)

    # Door Approach A
    print("\n--- Door Approach A (override pattern) ---")
    run_test("test_door_a_discovery", test_door_a_discovery)
    run_test("test_door_a_open_close_cycle", test_door_a_open_close_cycle)
    run_test("test_door_a_blocks_movement", test_door_a_blocks_movement)

    # Door Approach B
    print("\n--- Door Approach B (default pattern) ---")
    run_test("test_door_b_discovery", test_door_b_discovery)
    run_test("test_door_b_toggle", test_door_b_toggle)
    run_test("test_door_b_uses_default_field", test_door_b_uses_default_field)

    # Door spatial
    print("\n--- Door Spatial ---")
    run_test("test_door_vision_blocking", test_door_vision_blocking)

    # Lever
    print("\n--- Lever ---")
    run_test("test_lever_discovery", test_lever_discovery)
    run_test("test_lever_deactivates_trap", test_lever_deactivates_trap)
    run_test("test_lever_one_use", test_lever_one_use)

    # Chest
    print("\n--- Chest ---")
    run_test("test_chest_discovery", test_chest_discovery)
    run_test("test_chest_loot_transfers", test_chest_loot_transfers)
    run_test("test_empty_chest_no_action", test_empty_chest_no_action)
    run_test("test_chest_destroy_drops_loot", test_chest_destroy_drops_loot)

    # Campfire
    print("\n--- Campfire (multi-action) ---")
    run_test("test_campfire_multiple_actions", test_campfire_multiple_actions)
    run_test("test_campfire_execute_each", test_campfire_execute_each)

    # General
    print("\n--- General ---")
    run_test("test_out_of_range", test_out_of_range)
    run_test("test_non_usable_ignored", test_non_usable_ignored)
    run_test("test_charges_system", test_charges_system)

    print(f"\n{'=' * 60}")
    print(f"Results: {tests_passed} passed, {tests_failed} failed out of {tests_passed + tests_failed}")
    print(f"{'=' * 60}")

    if tests_failed > 0:
        sys.exit(1)
