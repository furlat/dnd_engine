"""Object spell contacts retain emitter geometry and cancellation protection."""

import pytest

from dnd.actions import SpellEvent
from dnd.actions_functional import execute_use_action
from dnd.content.items.authored_item_builders import build_authored_item
from dnd.content.items.environment_item_builders import build_spell_device
from dnd.core.base_actions import AvailableTarget
from dnd.core.creature_types import DamageType
from dnd.core.dice import fixed_dice_faces
from dnd.core.equipment_types import WeaponSlot
from dnd.core.events import EventHandler, EventPhase, EventQueue, EventType, TakeDamageEvent, Trigger
from dnd.entity import Entity
from dnd.runtime_reset import reset_engine_runtime
from dnd.spells.abjuration import GlobeOfInvulnerability
from dnd.spells.evocation import FireBolt, TrueStrike
from tests.engine.support import force_spell_attack_hit
from tests.manual.test_131_inventory_use_actions_legacy_contract import create_caster, item_action, reset_item_arena


@pytest.fixture(autouse=True)
def arena():
    reset_item_arena()
    yield
    reset_engine_runtime()


def prop(source, position):
    item = build_authored_item("environment.furniture.clay_stove", source.uuid)
    item.place_on_grid(position)
    return item


def cannon(source, *, range_feet):
    grant = FireBolt(source_entity_uuid=source.uuid, template=True,
        cast_origin="source_item", alt_range=range_feet, target_sector_degrees=45)
    item = build_spell_device(item_id="environment.fireball_cannon", name="Fire Bolt device",
        spell_templates=[grant], charges=1)
    item.place_on_grid((3, 5))
    return item


def test_object_spell_range_uses_device_emitter_in_discovery_and_execution():
    source = create_caster((2, 5))
    target = prop(source, (4, 5))
    device = cannon(source, range_feet=5)
    Entity.update_all_entities_senses()
    force_spell_attack_hit(source)
    info = item_action(source, device.uuid, "Fire Bolt")
    selection = next(row for row in info.valid_targets if row.target_uuid == target.uuid)
    assert selection.distance == 5
    before = target.get_hp()
    with fixed_dice_faces(18, 2):
        result = execute_use_action(source, device.uuid, info.template_name, selection)
    assert isinstance(result, SpellEvent) and not result.canceled
    assert result.effect_source_position == (3, 5)
    assert result.target_kind == "object" and result.target_position == (4, 5)
    assert target.get_hp() < before and device.charges == 0


@pytest.mark.parametrize("target_kind", ["object", "creature"])
def test_mixed_spell_targeting_rechecks_device_sector_without_spending(target_kind):
    source = create_caster((2, 5))
    target = prop(source, (3, 7)) if target_kind == "object" else create_caster((3, 7))
    device = cannon(source, range_feet=30)
    Entity.update_all_entities_senses()
    action = device.get_use_actions(source.uuid)[0]
    before = target.get_hp()
    result = execute_use_action(source, device.uuid, action.get_discovery_template_name(),
        AvailableTarget(index=0, target_uuid=target.uuid, target_kind=target_kind))
    assert result is not None and result.canceled
    assert "firing sector" in (result.status_message or "")
    assert target.get_hp() == before and device.charges == 1
    assert source.action_economy.actions.normalized_score == 1


def test_canceled_object_spell_effect_does_not_roll_or_apply_damage():
    source = create_caster((2, 5))
    target = prop(source, (4, 5))
    Entity.update_all_entities_senses()
    force_spell_attack_hit(source)

    def stop_effect(event, _source):
        if isinstance(event, SpellEvent) and event.target_entity_uuid == target.uuid:
            return event.cancel(status_message="Stopped at impact")
        return event

    EventQueue.add_event_handler(EventHandler(name="Stop object spell impact",
        source_entity_uuid=source.uuid,
        trigger_conditions=[Trigger(event_type=EventType.CAST_SPELL, event_phase=EventPhase.EFFECT)],
        event_processor=stop_effect))
    before = target.get_hp()
    cursor = EventQueue.event_cursor()
    with fixed_dice_faces(18):
        result = FireBolt(source_entity_uuid=source.uuid, target_entity_uuid=target.uuid).apply()
    assert result is not None and result.canceled
    assert target.get_hp() == before
    assert not any(isinstance(event, TakeDamageEvent) for _, event in EventQueue.iter_events_since(cursor))
    assert source.action_economy.actions.normalized_score == 0


def test_globe_blocks_fire_bolt_against_an_object_before_damage():
    source = create_caster((1, 5))
    owner = create_caster((6, 5))
    target = prop(source, (6, 5))
    Entity.update_all_entities_senses()
    globe = GlobeOfInvulnerability(source_entity_uuid=owner.uuid, costs=[], alt_skip_slot=True).apply()
    assert globe is not None and not globe.canceled
    before = target.get_hp()
    cursor = EventQueue.event_cursor()
    result = FireBolt(source_entity_uuid=source.uuid, target_entity_uuid=target.uuid).apply()
    assert result is not None and result.canceled
    assert result.outcome_code == "spell.globe_of_invulnerability.blocked"
    assert target.get_hp() == before
    assert not any(isinstance(event, TakeDamageEvent) for _, event in EventQueue.iter_events_since(cursor))


def test_fire_bolt_rechecks_object_after_execution_handlers_destroy_it():
    source = create_caster((2, 5))
    target = prop(source, (4, 5))
    Entity.update_all_entities_senses()

    def destroy_target(event, _source):
        if isinstance(event, SpellEvent) and event.target_entity_uuid == target.uuid:
            target.receive_damage(1000, DamageType.BLUDGEONING, source.uuid, parent_event=event)
        return event

    EventQueue.add_event_handler(EventHandler(name="Earlier impact destroys object",
        source_entity_uuid=source.uuid,
        trigger_conditions=[Trigger(event_type=EventType.CAST_SPELL, event_phase=EventPhase.EXECUTION)],
        event_processor=destroy_target))
    with fixed_dice_faces():
        result = FireBolt(source_entity_uuid=source.uuid, target_entity_uuid=target.uuid).apply()
    assert result is not None and result.canceled
    assert not target.is_breakable() and target.get_hp() <= 0
    assert source.action_economy.actions.normalized_score == 0


def test_true_strike_uses_selected_bow_range_for_an_object():
    source = create_caster((2, 5))
    bow = build_authored_item("weapon.longbow", source.uuid)
    assert source.inventory.add_item(bow)
    assert source.equip_item(bow.uuid, WeaponSlot.RANGED_MAIN)
    target = prop(source, (8, 5))
    Entity.update_all_entities_senses()
    action = TrueStrike(source_entity_uuid=source.uuid, target_entity_uuid=target.uuid,
        weapon_slot=WeaponSlot.RANGED_MAIN)
    before = target.get_hp()
    with fixed_dice_faces(18, 2):
        result = action.apply()
    assert result is not None and not result.canceled
    assert target.get_hp() < before
    assert source.action_economy.actions.normalized_score == 0
