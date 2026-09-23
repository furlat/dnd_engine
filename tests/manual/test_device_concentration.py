"""A destructible device owns independent sustained casts through native links."""

from dnd.actions import AttackObject, DropConcentration, SpellEvent
from dnd.actions_functional import execute_available_action, execute_use_action, get_available_actions
from dnd.blocks.base_item import BaseItem, ItemLocationStateEvent
from dnd.conditions import Concentrating
from dnd.content.items.authored_item_builders import build_authored_item
from dnd.content.items.environment_item_builders import build_spell_device
from dnd.core.base_actions import AvailableTarget, TargetType
from dnd.core.base_block import BaseBlock
from dnd.core.base_conditions import BaseCondition
from dnd.core.creature_types import DamageType
from dnd.core.dice import fixed_dice_faces
from dnd.core.equipment_types import WeaponSlot
from dnd.core.events import EventPhase, EventQueue, EventType, SavingThrowEvent
from dnd.core.gridmap import get_map
from dnd.core.item_types import ItemIntegrity, ItemLocation
from dnd.entity import Entity
from dnd.spells.conjuration import Web, WebZone
from dnd.spells.enchantment import HoldPerson
from dnd.types.world import MovementMode
from tests.manual.test_131_inventory_use_actions_legacy_contract import (
    create_caster, create_target, force_save, item_action, reset_item_arena,
)


def setup_device(*, hit_points: int = 8):
    reset_item_arena(width=30)
    caster = create_caster((4, 10))
    targets = (create_target((8, 10), name="First"), create_target((13, 10), name="Second"))
    for target in targets:
        force_save(target, "dexterity", succeeds=False)
    device = build_spell_device(item_id="environment.arcane_machine_gun", name="Web Cannon",
        source_entity_uuid=caster.uuid, charges=4, hit_points=hit_points, concentration_capacity=2,
        spell_templates=[Web(source_entity_uuid=caster.uuid, template=True,
            cast_origin="source_item", target_sector_degrees=45)])
    device.place_on_grid((5, 10))
    Entity.update_all_entities_senses()
    return caster, targets, device


def cast_web(caster, device, position):
    info = item_action(caster, device.uuid, "Web")
    selected = next(row for row in info.valid_targets if row.position == position)
    with fixed_dice_faces(10):
        event = execute_use_action(caster, device.uuid, info.template_name, selected)
    assert isinstance(event, SpellEvent) and not event.canceled
    return event


def test_authored_device_hit_points_remain_exact_through_damage_and_public_snapshots() -> None:
    caster, _, device = setup_device(hit_points=12)
    initial = device.to_item_presentation_state()
    assert initial.current_hit_points == initial.maximum_hit_points == 12
    cursor = EventQueue.event_cursor()
    assert device.receive_damage(5, DamageType.FORCE, caster.uuid) == 5
    snapshots = [event.item_state for _, event in EventQueue.iter_events_since(cursor)
                 if isinstance(event, ItemLocationStateEvent)]
    assert snapshots and all(state.current_hit_points == 7 and state.maximum_hit_points == 12
                             for state in snapshots)
    assert get_map().get_object_position(device.uuid) == (5, 10)
    assert device.receive_damage(7, DamageType.FORCE, caster.uuid) == 7
    destroyed = device.to_item_presentation_state()
    assert destroyed.current_hit_points == 0 and destroyed.maximum_hit_points == 12
    assert get_map().get_object_position(device.uuid) == (5, 10)
    assert BaseBlock.get(device.uuid) is device and device.integrity is ItemIntegrity.DESTROYED


def test_device_has_two_distinct_web_slots_and_rejects_full_capacity_without_costs() -> None:
    caster, targets, device = setup_device()
    casts = []
    for target in targets:
        caster.action_economy.reset_all_costs()
        casts.append(cast_web(caster, device, target.position))
    concentration = device.active_conditions["Concentrating"]
    assert isinstance(concentration, Concentrating)
    assert len(concentration.concentration_slots) == 2
    assert len({slot.uuid for slot in concentration.concentration_slots.values()}) == 2
    assert "Concentrating" not in caster.active_conditions
    zones = [zone for zone in get_map().get_spatial_conditions() if isinstance(zone, WebZone)]
    assert len(zones) == 2 and all("Restrained" in target.active_conditions for target in targets)
    assert {zone.source_entity_uuid for zone in zones} == {caster.uuid}
    assert all(event.source_entity_uuid == caster.uuid and event.source_position == (4, 10) for event in casts)
    snapshot = device.to_item_presentation_state()
    assert snapshot.current_hit_points == snapshot.maximum_hit_points == 8
    assert snapshot.concentration_capacity == 2
    assert [slot.spell_id for slot in snapshot.concentration_slots] == ["spell.web", "spell.web"]
    for zone in zones:
        observed = caster.senses.spatial_effects[zone.uuid]
        assert observed.sustainer_item_uuid == device.uuid and observed.anchor_position == zone.position
        assert observed.concentration_slot_uuid in concentration.concentration_slots
    caster.action_economy.reset_all_costs()
    assert not any(row.source_item_uuid == device.uuid for row in get_available_actions(caster).all_actions)
    template = device.get_use_actions(caster.uuid)[0]
    charges, slots = device.charges, caster.action_economy.spell_slot_2.normalized_score
    result = execute_use_action(caster, device.uuid, template.get_discovery_template_name(),
        AvailableTarget(index=0, position=(17, 10)))
    assert result is not None and result.canceled and "capacity" in (result.status_message or "")
    assert device.charges == charges and caster.action_economy.actions.normalized_score == 1
    assert caster.action_economy.spell_slot_2.normalized_score == slots
    assert {zone.uuid for zone in get_map().get_spatial_conditions()} == {zone.uuid for zone in zones}


def test_independent_zone_removal_frees_only_its_device_slot_and_recast_reuses_capacity() -> None:
    caster, targets, device = setup_device()
    for target in targets:
        caster.action_economy.reset_all_costs()
        cast_web(caster, device, target.position)
    first = next(zone for zone in get_map().get_spatial_conditions()
                 if isinstance(zone, WebZone) and zone.position == targets[0].position)
    second = next(zone for zone in get_map().get_spatial_conditions()
                  if isinstance(zone, WebZone) and zone.position == targets[1].position)
    old_slots = {slot.slot_uuid for slot in device.to_item_presentation_state().concentration_slots}
    assert first.deactivate() is not None
    remaining = device.to_item_presentation_state().concentration_slots
    assert len(remaining) == 1 and remaining[0].slot_uuid in old_slots
    assert get_map().get_spatial_condition(second.uuid) is second
    assert "Restrained" not in targets[0].active_conditions and "Restrained" in targets[1].active_conditions
    caster.action_economy.reset_all_costs()
    cast_web(caster, device, targets[0].position)
    new_slots = {slot.slot_uuid for slot in device.to_item_presentation_state().concentration_slots}
    assert len(new_slots) == 2 and len(new_slots - old_slots) == 1


def test_operator_concentration_is_independent_and_object_attack_destroys_all_device_webs() -> None:
    caster, targets, device = setup_device()
    for target in targets:
        caster.action_economy.reset_all_costs()
        cast_web(caster, device, target.position)
    zones = tuple(get_map().get_spatial_conditions())
    caster.action_economy.reset_all_costs()
    ordinary = Web(source_entity_uuid=caster.uuid, end_position=(4, 15)).apply()
    assert ordinary is not None and not ordinary.canceled
    assert "Concentrating" in caster.active_conditions and "Concentrating" in device.active_conditions
    drop = DropConcentration(source_entity_uuid=caster.uuid).apply()
    assert drop is not None and not drop.canceled
    assert all(get_map().get_spatial_condition(zone.uuid) is zone for zone in zones)
    caster.receive_damage(1, DamageType.FORCE, source_entity_uuid=caster.uuid)
    cursor = EventQueue.event_cursor()
    assert device.receive_damage(1, DamageType.FORCE, caster.uuid) == 1
    events = [event for _, event in EventQueue.iter_events_since(cursor)]
    assert not any(isinstance(event, SavingThrowEvent) for event in events)
    assert any(isinstance(event, ItemLocationStateEvent) and event.item_state.current_hit_points == 7
               for event in events)
    weapon = build_authored_item("weapon.greataxe", caster.uuid)
    caster.loot_item(weapon)
    assert caster.equip_item(weapon.uuid, WeaponSlot.MELEE_MAIN)
    caster.action_economy.reset_all_costs()
    available = get_available_actions(caster)
    assert any(row.behavior_id == "action.attack_object" and any(choice.target_uuid == device.uuid
               for choice in row.valid_targets) for row in available.all_actions)
    cursor = EventQueue.event_cursor()
    with fixed_dice_faces(12):
        attack = AttackObject(source_entity_uuid=caster.uuid, target_entity_uuid=device.uuid).apply()
    assert attack is not None and not attack.canceled and attack.phase is EventPhase.COMPLETION
    assert get_map().get_object_position(device.uuid) == (5, 10)
    assert BaseBlock.get(device.uuid) is device and device.integrity is ItemIntegrity.DESTROYED
    assert not device.active_conditions and not device.to_item_presentation_state().concentration_slots
    assert all(get_map().get_spatial_condition(zone.uuid) is None for zone in zones)
    assert all(BaseCondition.get(zone.uuid) is None for zone in zones)
    assert all("Restrained" not in target.active_conditions for target in targets)
    for target in targets:
        tile = get_map().get_tile(*target.position)
        assert tile is not None and tile.get_movement_cost(MovementMode.WALKING) == 1
    events = [event for _, event in EventQueue.iter_events_since(cursor)]
    completed = [event for event in events if event.phase is EventPhase.COMPLETION]
    assert [event.lineage_uuid for event in completed if event.parent_lineage is None] == [attack.lineage_uuid]
    assert any(event.event_type is EventType.CONDITION_REMOVAL for event in completed)
    destroyed = next(event for event in completed if isinstance(event, ItemLocationStateEvent)
                     and event.location is ItemLocation.FLOOR
                     and event.item_state.integrity is ItemIntegrity.DESTROYED)
    assert destroyed.replacement_item_uuid is None
    assert destroyed.item_state.item_uuid == device.uuid
    assert destroyed.item_state.item_id == "environment.arcane_machine_gun"
    assert not device.active_conditions and not device.to_item_presentation_state().concentration_slots


def test_one_multitarget_device_cast_uses_one_slot_and_last_child_releases_it() -> None:
    caster, targets, device = setup_device()
    device.use_action_templates = [HoldPerson(source_entity_uuid=caster.uuid, template=True,
        cast_origin="source_item", target_type=TargetType.MULTI_ENTITY, alt_target_count=2)]
    for target in targets:
        force_save(target, "wisdom", succeeds=False)
    info = item_action(caster, device.uuid, "Hold Person")
    selected = next(row for row in info.valid_targets if row.target_uuid == targets[0].uuid)
    with fixed_dice_faces(10, 10):
        result = execute_available_action(caster, info, selected,
            extra_target_uuids=[str(targets[1].uuid)])
    assert result is not None and not result.canceled
    concentration = device.active_conditions["Concentrating"]
    assert isinstance(concentration, Concentrating) and len(concentration.concentration_slots) == 1
    assert len(concentration.linked_conditions) == 2
    assert all("Paralyzed" in target.active_conditions for target in targets)
    assert targets[0].remove_condition("Hold Person")
    assert len(device.to_item_presentation_state().concentration_slots) == 1
    assert targets[1].remove_condition("Hold Person")
    assert "Concentrating" not in device.active_conditions
    assert not device.to_item_presentation_state().concentration_slots


def test_mage_second_web_still_replaces_its_first_concentration() -> None:
    caster, targets, _ = setup_device()
    with fixed_dice_faces(10):
        first = Web(source_entity_uuid=caster.uuid, end_position=targets[0].position).apply()
    assert first is not None and not first.canceled
    first_zone = next(zone for zone in get_map().get_spatial_conditions() if isinstance(zone, WebZone))
    caster.action_economy.reset_all_costs()
    with fixed_dice_faces(10):
        second = Web(source_entity_uuid=caster.uuid, end_position=targets[1].position).apply()
    assert second is not None and not second.canceled
    assert get_map().get_spatial_condition(first_zone.uuid) is None
    assert len(get_map().get_spatial_conditions()) == 1
    assert "Restrained" not in targets[0].active_conditions and "Restrained" in targets[1].active_conditions
    concentration = caster.active_conditions["Concentrating"]
    assert isinstance(concentration, Concentrating) and len(concentration.concentration_slots) == 1
