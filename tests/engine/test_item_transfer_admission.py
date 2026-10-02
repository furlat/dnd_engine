"""Accepted item transitions preserve one physical identity and its ownership."""
from uuid import uuid4

import pytest

from dnd.actions import PickUp
from dnd.actions_functional import execute_by_index, execute_use_action, setup_standard_actions
from dnd.blocks.base_item import BaseItem, ItemHoldingsReleasedEvent, ItemLocationStateEvent, UsableItem, WorldItem
from dnd.content.items.authored_item_builders import build_authored_item
from dnd.content.items.environment_item_builders import build_storage_chest
from dnd.core.base_block import BaseBlock
from dnd.core.creature_types import DamageType
from dnd.core.events import EventHandler, EventPhase, EventQueue, EventType, SpatialChangeEvent, Trigger
from dnd.core.equipment_types import WeaponSlot
from dnd.core.gridmap import get_map
from dnd.core.item_types import ItemIntegrity, ItemLocation
from dnd.entity import Entity, EntityConfig
from dnd.game import Game
from dnd.runtime_reset import reset_engine_runtime
from dnd.types.world_placement import WorldPlacementKind, WorldPlacementSpec


@pytest.fixture(autouse=True)
def runtime():
    reset_engine_runtime(grid_size=(6, 4))


def actor(game, name="Collector", position=(1, 1)):
    entity = Entity.create(uuid4(), name, config=EntityConfig())
    entity.compose_entity()
    game.deploy_entity(entity, position)
    return entity


def loose(owner, name="Key", **kwargs):
    return BaseItem(source_entity_uuid=owner.uuid, item_id="test.item.key", name=name, **kwargs)


def veto(owner, event_type, phase, item_uuid):
    handler = EventHandler(
        name="Reject item placement change", source_entity_uuid=owner.uuid,
        trigger_conditions=[Trigger(event_type=event_type, event_phase=phase)],
        event_processor=lambda event, _: event.cancel(status_message="Rejected transfer")
            if isinstance(event, SpatialChangeEvent) and event.object_uuid == item_uuid else event,
    )
    EventQueue.add_event_handler(handler)
    return handler


def location_facts_since(cursor, item_uuid):
    return [event for _, event in EventQueue.iter_events_since(cursor)
            if isinstance(event, ItemLocationStateEvent) and event.phase is EventPhase.COMPLETION
            and event.item_state.item_uuid == item_uuid]


@pytest.mark.parametrize("phase", [EventPhase.DECLARATION, EventPhase.EXECUTION, EventPhase.EFFECT])
def test_rejected_pickup_preserves_floor_source_and_reports_action_failure(phase):
    game = Game()
    entity = actor(game)
    item = loose(entity)
    item.source_entity_uuid = uuid4()
    original_source = item.source_entity_uuid
    item.place_on_grid((2, 1))
    entity.update_entity_senses()
    handler = veto(entity, EventType.SPATIAL_OBJECT_REMOVED, phase, item.uuid)
    cursor = EventQueue.event_cursor()
    try:
        result = PickUp(source_entity_uuid=entity.uuid, target_entity_uuid=item.uuid).apply()
        assert result is not None and result.canceled
        assert not entity.inventory.has_item(item.uuid)
        assert get_map().get_object_position(item.uuid) == (2, 1)
        assert item.tile_uuid is not None
        assert item.owner_uuid is None and item.stored_in_uuid is None
        assert item.source_entity_uuid == original_source
        assert not location_facts_since(cursor, item.uuid)
    finally:
        EventQueue.remove_event_handler(handler)


@pytest.mark.parametrize("phase", [EventPhase.DECLARATION, EventPhase.EXECUTION, EventPhase.EFFECT])
def test_rejected_drop_preserves_inventory_and_can_be_retried(phase):
    game = Game()
    entity = actor(game)
    item = loose(entity)
    assert entity.loot_item(item)
    handler = veto(entity, EventType.SPATIAL_OBJECT_PLACED, phase, item.uuid)
    cursor = EventQueue.event_cursor()
    try:
        assert entity.drop_item(item.uuid, (2, 1)) is None
        assert entity.inventory.items[item.uuid] is item
        assert item.owner_uuid == entity.uuid and item.stored_in_uuid == entity.inventory.uuid
        assert item.tile_uuid is None and get_map().get_object_position(item.uuid) is None
        assert not location_facts_since(cursor, item.uuid)
    finally:
        EventQueue.remove_event_handler(handler)
    assert entity.drop_item(item.uuid, (2, 1)) is item
    facts = location_facts_since(cursor, item.uuid)
    assert len(facts) == 1 and facts[0].location is ItemLocation.FLOOR


def test_full_inventory_transfer_keeps_original_container_without_rollback_merge():
    game = Game()
    first = actor(game)
    second = actor(game, "Receiver", (2, 1))
    item = loose(first)
    assert first.loot_item(item)
    second.inventory.max_slots = 0
    cursor = EventQueue.event_cursor()
    assert not first.inventory.transfer_to(item.uuid, second.inventory)
    assert first.inventory.items[item.uuid] is item
    assert item.owner_uuid == first.uuid and item.stored_in_uuid == first.inventory.uuid
    assert not [event for _, event in EventQueue.iter_events_since(cursor)
                if isinstance(event, ItemHoldingsReleasedEvent)]
    second.inventory.max_slots = 1
    assert first.inventory.transfer_to(item.uuid, second.inventory)
    assert not first.inventory.has_item(item.uuid) and second.inventory.items[item.uuid] is item
    assert item.owner_uuid == second.uuid and item.stored_in_uuid == second.inventory.uuid
    release, = [event for _, event in EventQueue.iter_events_since(cursor)
                if isinstance(event, ItemHoldingsReleasedEvent) and event.phase is EventPhase.COMPLETION]
    assert release.item_uuid == item.uuid and release.source_entity_uuid == first.uuid
    assert release.previous_container_uuid == first.inventory.uuid
    assert release.target_entity_uuid is None


def test_destination_occupied_during_drop_admission_keeps_item_in_inventory():
    game = Game()
    entity = actor(game)
    spec = WorldPlacementSpec(kind=WorldPlacementKind.CENTER, occupies_bands=True,
                              vertical_extent_steps=1)
    item = WorldItem(source_entity_uuid=entity.uuid, item_id="test.item.portable_box",
                     world_placement_spec=spec)
    obstruction = WorldItem(source_entity_uuid=entity.uuid, item_id="test.item.obstruction",
                            world_placement_spec=spec)
    assert entity.loot_item(item)

    def occupy_destination(event, _):
        if isinstance(event, SpatialChangeEvent) and event.object_uuid == item.uuid:
            obstruction.place_on_grid((2, 1))
        return event

    handler = EventHandler(name="Destination changes before commit", source_entity_uuid=entity.uuid,
        trigger_conditions=[Trigger(event_type=EventType.SPATIAL_OBJECT_PLACED,
                                    event_phase=EventPhase.EFFECT)], event_processor=occupy_destination)
    EventQueue.add_event_handler(handler)
    try:
        assert entity.drop_item(item.uuid, (2, 1)) is None
        assert entity.inventory.items[item.uuid] is item
        assert item.owner_uuid == entity.uuid and item.stored_in_uuid == entity.inventory.uuid
        assert get_map().get_object_position(item.uuid) is None
        assert get_map().get_object_position(obstruction.uuid) == (2, 1)
    finally:
        EventQueue.remove_event_handler(handler)


def test_initially_occupied_drop_returns_failure_without_detaching_item():
    game = Game()
    entity = actor(game)
    spec = WorldPlacementSpec(kind=WorldPlacementKind.CENTER, occupies_bands=True,
                              vertical_extent_steps=1)
    item = WorldItem(source_entity_uuid=entity.uuid, item_id="test.item.portable_box",
                     world_placement_spec=spec)
    obstruction = WorldItem(source_entity_uuid=entity.uuid, item_id="test.item.obstruction",
                            world_placement_spec=spec)
    assert entity.loot_item(item)
    obstruction.place_on_grid((2, 1))
    assert entity.drop_item(item.uuid, (2, 1)) is None
    assert entity.inventory.items[item.uuid] is item
    assert item.owner_uuid == entity.uuid and item.stored_in_uuid == entity.inventory.uuid


def test_state_bearing_or_different_recipe_stacks_keep_distinct_identities():
    game = Game()
    entity = actor(game)
    first = loose(entity, stack_id="keys", max_stack=5)
    second = loose(entity, stack_id="keys", max_stack=5)
    second.add_event_handler(EventHandler(
        name="Owned effect", source_entity_uuid=entity.uuid,
        trigger_conditions=[Trigger(event_type=EventType.TURN_START, event_phase=EventPhase.EFFECT)],
        event_processor=lambda event, _: event,
    ))
    third = BaseItem(source_entity_uuid=entity.uuid, item_id="test.item.other_key",
                     stack_id="keys", max_stack=5)
    for item in first, second, third:
        assert entity.loot_item(item)
    assert len(entity.inventory.items) == 3
    assert all(BaseBlock.get(item.uuid) is item for item in (first, second, third))


def test_spent_charge_stack_does_not_merge_with_pristine_stack():
    game = Game()
    entity = actor(game)
    items = [UsableItem(source_entity_uuid=entity.uuid, item_id="test.item.charged",
                        stack_id="charged", max_stack=5, charges=charges, max_charges=2)
             for charges in (1, 2)]
    for item in items:
        assert entity.loot_item(item)
    assert len(entity.inventory.items) == 2
    assert [item.charges for item in items] == [1, 2]


def test_damageable_stack_copies_preserve_individual_health():
    game = Game()
    entity = actor(game)
    items = [loose(entity, stack_id="damageable", max_stack=5) for _ in range(2)]
    for item in items:
        item.health = item.create_item_health(item.uuid, 16)
    items[1].receive_damage(8, DamageType.BLUDGEONING, entity.uuid)
    for item in items:
        assert entity.loot_item(item)
    assert len(entity.inventory.items) == 2
    assert [item.get_hp() for item in items] == [16, 8]


def test_rejected_equipment_overflow_preserves_slots_and_incoming_item():
    game = Game()
    entity = actor(game)
    main = build_authored_item("weapon.shortsword", entity.uuid)
    off = build_authored_item("weapon.dagger", entity.uuid)
    replacement = build_authored_item("weapon.greatsword", entity.uuid)
    for item, slot in ((main, WeaponSlot.MELEE_MAIN), (off, WeaponSlot.MELEE_OFF)):
        assert entity.loot_item(item) and entity.equip_item(item.uuid, slot)
    assert entity.loot_item(replacement)
    entity.inventory.max_slots = 1
    handler = veto(entity, EventType.SPATIAL_OBJECT_PLACED, EventPhase.EFFECT, off.uuid)
    try:
        assert not entity.equip_item(replacement.uuid, WeaponSlot.MELEE_MAIN)
        assert entity.equipment.get_weapon(WeaponSlot.MELEE_MAIN) is main
        assert entity.equipment.get_weapon(WeaponSlot.MELEE_OFF) is off
        assert entity.inventory.items[replacement.uuid] is replacement
        assert main.is_equipped and off.is_equipped
        assert get_map().get_object_position(off.uuid) is None
    finally:
        EventQueue.remove_event_handler(handler)
    assert entity.equip_item(replacement.uuid, WeaponSlot.MELEE_MAIN)
    assert entity.inventory.items[main.uuid] is main
    assert get_map().get_object_position(off.uuid) == entity.position


def test_rejected_unequip_overflow_preserves_equipped_property():
    game = Game()
    entity = actor(game)
    weapon = build_authored_item("weapon.shortsword", entity.uuid)
    assert entity.loot_item(weapon) and entity.equip_item(weapon.uuid, WeaponSlot.MELEE_MAIN)
    entity.inventory.max_slots = 0
    handler = veto(entity, EventType.SPATIAL_OBJECT_PLACED, EventPhase.EFFECT, weapon.uuid)
    try:
        assert entity.unequip_item(WeaponSlot.MELEE_MAIN) is None
        assert entity.equipment.get_weapon(WeaponSlot.MELEE_MAIN) is weapon
        assert weapon.is_equipped and weapon.stored_in_uuid == entity.equipment.uuid
    finally:
        EventQueue.remove_event_handler(handler)


def test_direct_equipment_api_respects_floor_removal_veto_before_slot_commit():
    game = Game()
    entity = actor(game)
    weapon = build_authored_item("weapon.shortsword", entity.uuid)
    weapon.place_on_grid((2, 1))
    handler = veto(entity, EventType.SPATIAL_OBJECT_REMOVED, EventPhase.EFFECT, weapon.uuid)
    try:
        assert not entity.equipment.equip(weapon, WeaponSlot.MELEE_MAIN)
        assert entity.equipment.get_weapon(WeaponSlot.MELEE_MAIN) is None
        assert not weapon.is_equipped and weapon.owner_uuid is None
        assert get_map().get_object_position(weapon.uuid) == (2, 1)
    finally:
        EventQueue.remove_event_handler(handler)
    assert entity.equipment.equip(weapon, WeaponSlot.MELEE_MAIN)
    assert get_map().get_object_position(weapon.uuid) is None
    assert weapon.is_equipped and weapon.tile_uuid is None


def test_transfers_require_ordinary_unequip_before_changing_equipped_ownership():
    game = Game()
    first = actor(game)
    second = actor(game, "Recipient", (2, 1))
    weapon = build_authored_item("weapon.dagger", first.uuid)
    assert first.loot_item(weapon) and first.equip_item(weapon.uuid, WeaponSlot.MELEE_MAIN)
    handler = EventHandler(name="Unequip requires permission from its native rule",
        source_entity_uuid=first.uuid, validation_only=True,
        trigger_conditions=[Trigger(event_type=EventType.WEAPON_UNEQUIP,
                                    event_phase=EventPhase.EXECUTION)],
        event_processor=lambda event, _: event.cancel(status_message="Unequip rejected"))
    EventQueue.add_event_handler(handler)
    assert first.unequip_item(WeaponSlot.MELEE_MAIN) is None
    assert not second.loot_item(weapon)
    assert not second.equipment.equip(weapon, WeaponSlot.MELEE_MAIN)
    assert first.equipment.get_weapon(WeaponSlot.MELEE_MAIN) is weapon
    assert weapon.is_equipped and weapon.owner_uuid == first.uuid
    EventQueue.remove_event_handler(handler)
    assert first.unequip_item(WeaponSlot.MELEE_MAIN) is weapon
    assert second.loot_item(weapon) and second.equip_item(weapon.uuid, WeaponSlot.MELEE_MAIN)
    assert first.equipment.get_weapon(WeaponSlot.MELEE_MAIN) is None
    assert second.equipment.get_weapon(WeaponSlot.MELEE_MAIN) is weapon


def test_chest_break_keeps_rejected_spill_lootable_in_the_same_wreck():
    game = Game()
    entity = actor(game)
    chest = build_storage_chest("Chest", include_loot_all_action=True)
    chest.chest_inventory.source_entity_uuid = chest.uuid
    item = loose(chest)
    assert chest.chest_inventory.add_item(item)
    chest.place_on_grid((2, 1))
    handler = veto(entity, EventType.SPATIAL_OBJECT_PLACED, EventPhase.EFFECT, item.uuid)
    try:
        chest.destroy()
        assert chest.integrity is ItemIntegrity.DESTROYED
        assert BaseBlock.get(chest.uuid) is chest
        assert chest.chest_inventory.items[item.uuid] is item
        assert item.owner_uuid == chest.uuid and item.stored_in_uuid == chest.chest_inventory.uuid
        assert get_map().get_object_position(item.uuid) is None
    finally:
        EventQueue.remove_event_handler(handler)
    entity.update_entity_senses()
    available = entity.get_available_actions()
    row = next(row for row in available.all_actions if row.source_item_uuid == chest.uuid
               and row.display_name.startswith("Loot All"))
    result = execute_use_action(entity, chest.uuid, row.template_name)
    assert result is not None and not result.canceled, result.status_message if result else "No result"
    assert entity.inventory.items[item.uuid] is item and not chest.chest_inventory.items
    assert not chest.get_use_actions(entity.uuid)


def test_discovered_drop_executes_the_bound_item_and_expires_its_affordance():
    game = Game()
    entity = actor(game)
    first, second = loose(entity, "First"), loose(entity, "Second")
    assert entity.loot_item(first) and entity.loot_item(second)
    setup_standard_actions(entity)
    entity.update_entity_senses()
    available = entity.get_available_actions()
    rows = [row for row in available.all_actions if row.behavior_id == "action.core.drop"]
    assert len(rows) == 2 and {row.source_item_uuid for row in rows} == {first.uuid, second.uuid}
    row = next(row for row in rows if row.source_item_uuid == first.uuid)
    target = next(target for target in row.valid_targets if target.position == entity.position)
    result = execute_by_index(entity, row.template_name, target.index, available=available)
    assert result is not None and not result.canceled, result.status_message if result else "No result"
    assert get_map().get_object_position(first.uuid) == entity.position
    assert entity.inventory.items[second.uuid] is second
    assert [row.source_item_uuid for row in entity.get_available_actions().all_actions
            if row.behavior_id == "action.core.drop"] == [second.uuid]
