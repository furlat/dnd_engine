"""Real object damage leaves inert, observable debris under the same cause."""

import pytest

from dnd.actions import AttackObject
from dnd.actions_functional import execute_use_action, get_available_actions
from dnd.blocks.base_item import BaseItem, ItemLocationStateEvent
from dnd.content.items.authored_item_builders import build_authored_item
from dnd.content.items.environment_item_builders import build_spell_device
from dnd.core.base_block import BaseBlock
from dnd.core.creature_types import DamageType
from dnd.core.dice import fixed_dice_faces
from dnd.core.equipment_types import WeaponSlot
from dnd.core.events import EventPhase, EventQueue, ItemDestructionEvent, SensoryUpdateEvent, TakeDamageEvent
from dnd.core.gridmap import get_map
from dnd.core.item_types import ItemIntegrity, ItemLocation
from dnd.entity import Entity
from dnd.spells.enchantment import Sleep
from dnd.spells.evocation import Fireball
from dnd.types.world import CardinalDirection
from tests.manual.test_131_inventory_use_actions_legacy_contract import (
    create_caster, create_target, reset_item_arena,
)


@pytest.mark.parametrize("body, spell_type", (
    ("environment.fireball_cannon", Sleep),
    ("environment.arcane_machine_gun", Fireball),
))
def test_object_attacks_leave_body_specific_inert_wreck_discoverable_later(body, spell_type) -> None:
    reset_item_arena()
    caster = create_caster((4, 10))
    weapon = build_authored_item("weapon.longsword", caster.uuid)
    caster.loot_item(weapon)
    assert caster.equip_item(weapon.uuid, WeaponSlot.MELEE_MAIN)
    grant = spell_type(source_entity_uuid=caster.uuid, template=True)
    device = build_spell_device(item_id=body, name="Test device", source_entity_uuid=caster.uuid,
        spell_templates=[grant], hit_points=12)
    initial = device.to_item_presentation_state()
    original = device.place_on_grid((5, 10), base_height_steps=2, orientation=CardinalDirection.SOUTH)
    Entity.update_all_entities_senses()
    cursor = EventQueue.event_cursor()
    caster.action_economy.reset_all_costs()
    with fixed_dice_faces(4):
        hit = AttackObject(source_entity_uuid=caster.uuid, target_entity_uuid=device.uuid).apply()
    assert hit is not None and not hit.canceled
    assert device.get_hp() == 8 and get_map().get_object_placement(device.uuid) == original
    assert not any(isinstance(event, ItemDestructionEvent)
                   for _, event in EventQueue.iter_events_since(cursor))

    caster.action_economy.reset_all_costs()
    cursor = EventQueue.event_cursor()
    with fixed_dice_faces(8):
        lethal = AttackObject(source_entity_uuid=caster.uuid, target_entity_uuid=device.uuid).apply()
    assert lethal is not None and not lethal.canceled
    completed = [event for _, event in EventQueue.iter_events_since(cursor)
                 if event.phase is EventPhase.COMPLETION]
    destroyed = [event for event in completed if isinstance(event, ItemDestructionEvent)]
    assert len(destroyed) == 1
    fact = destroyed[0]
    assert fact.item_uuid == device.uuid
    assert fact.previous_state.item_id == body and fact.previous_state.integrity is ItemIntegrity.INTACT
    assert fact.resulting_state is not None
    assert fact.resulting_state.current_hit_points == 0
    assert fact.resulting_state.integrity is ItemIntegrity.DESTROYED
    damage = next(event for event in completed if isinstance(event, TakeDamageEvent))
    assert fact.parent_lineage == damage.lineage_uuid and damage.parent_lineage == lethal.lineage_uuid
    assert [event.lineage_uuid for event in completed if event.parent_lineage is None] == [lethal.lineage_uuid]
    assert BaseBlock.get(device.uuid) is device and device.uuid in caster.senses.objects
    placement = get_map().get_object_placement(device.uuid)
    assert placement is not None
    assert (placement.position, placement.tile_uuid, placement.base_height_steps, placement.orientation) == (
        original.position, original.tile_uuid, original.base_height_steps, original.orientation)
    state = device.to_item_presentation_state()
    assert state.item_id == body and state.item_uuid == initial.item_uuid
    assert state.current_hit_points == 0 and state.maximum_hit_points == initial.maximum_hit_points
    assert state.charges == initial.charges and state.max_charges == initial.max_charges
    assert state.concentration_capacity == initial.concentration_capacity and state.concentration_slots == ()
    assert not device.active_conditions
    assert not any((state.is_usable, state.is_targetable, state.is_pickable, state.is_equippable,
                    state.include_in_available_object_actions, state.blocks_movement,
                    state.blocks_optics, state.blocks_propagation))
    assert state.is_lit is None
    caster.action_economy.reset_all_costs()
    assert not any(row.source_item_uuid == device.uuid or any(target.target_uuid == device.uuid
                   for target in row.valid_targets) for row in get_available_actions(caster).all_actions)
    with pytest.raises(ValueError, match="not found on item"):
        execute_use_action(caster, device.uuid, grant.name)

    cursor = EventQueue.event_cursor()
    arriving = create_target((6, 10), name="Late observer")
    Entity.update_all_entities_senses()
    assert device.uuid in arriving.senses.objects
    observations = [event for _, event in EventQueue.iter_events_since(cursor)
                    if isinstance(event, SensoryUpdateEvent) and event.observer_uuid == arriving.uuid]
    assert any(device.uuid in event.object_contacts_changed for event in observations)
    assert not any(isinstance(event, ItemDestructionEvent)
                   for _, event in EventQueue.iter_events_since(cursor))


@pytest.mark.parametrize("held", (False, True))
def test_unplaced_or_held_device_destruction_does_not_spawn_a_floor_wreck(held) -> None:
    reset_item_arena()
    caster = create_caster((4, 10))
    device = build_spell_device(item_id="environment.arcane_machine_gun", name="Test device",
        source_entity_uuid=caster.uuid, spell_templates=[], hit_points=8)
    if held:
        caster.loot_item(device)
        assert device.owner_uuid == caster.uuid
    before = get_map().get_all_object_positions()
    cursor = EventQueue.event_cursor()
    assert device.receive_damage(8, DamageType.FORCE, caster.uuid) == 8
    destroyed = [event for _, event in EventQueue.iter_events_since(cursor)
                 if isinstance(event, ItemDestructionEvent) and event.phase is EventPhase.COMPLETION]
    assert len(destroyed) == 1 and destroyed[0].item_uuid == device.uuid
    assert BaseBlock.get(device.uuid) is device and device.integrity is ItemIntegrity.DESTROYED
    assert get_map().get_all_object_positions() == before
    if held:
        assert device.owner_uuid == caster.uuid and caster.inventory.has_item(device.uuid)
    else:
        assert device.owner_uuid is None and device.stored_in_uuid is None


def test_ordinary_breakable_item_destruction_has_no_replacement() -> None:
    reset_item_arena()
    caster = create_caster((4, 10))
    item = BaseItem(source_entity_uuid=caster.uuid, item_id="environment.test_crate",
                    name="Crate", is_targetable=True)
    item.health = item.create_item_health(item.uuid, 4)
    item.place_on_grid((5, 10))
    cursor = EventQueue.event_cursor()
    item.receive_damage(4, DamageType.FORCE, caster.uuid)
    destroyed = [event for _, event in EventQueue.iter_events_since(cursor)
                 if isinstance(event, ItemLocationStateEvent) and event.location is ItemLocation.DESTROYED]
    assert len(destroyed) == 1 and destroyed[0].replacement_item_uuid is None
    assert not get_map().get_objects_at((5, 10))
