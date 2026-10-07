"""Finite item release is terminal once, including canceled and recharged uses."""
from uuid import uuid4

import pytest

from dnd.actions_functional import execute_use_action, setup_standard_actions
from dnd.blocks.base_item import ItemResourceChangeEvent, UsableItem
from dnd.content.items.authored_item_builders import build_authored_item
from dnd.core.equipment_types import BodyPart
from dnd.core.events import Event, EventHandler, EventPhase, EventQueue, EventType, Trigger
from dnd.core.item_types import ItemResourceChange
from dnd.entity import Entity
from dnd.game import Game
from dnd.runtime_reset import reset_engine_runtime
from dnd.player.event_record import decode_event, encode_event


@pytest.fixture
def equipped_pack():
    reset_engine_runtime(grid_size=(8, 8))
    game = Game()
    owner = Entity.create(uuid4(), "Wearer")
    owner.compose_entity()
    game.deploy_entity(owner, (3, 3))
    setup_standard_actions(owner)
    pack = build_authored_item("gear.wayfarer_pack", owner.uuid)
    assert isinstance(pack, UsableItem)
    assert owner.loot_item(pack) and owner.equip_item(pack.uuid, BodyPart.BACKPACK)
    yield owner, pack
    game.close()
    reset_engine_runtime()


def prepare(owner, pack):
    parent = Event(source_entity_uuid=owner.uuid, event_type=EventType.BASE_ACTION)
    return pack.prepare_charge_consumption(1, owner.uuid, parent)


def terminal_versions(prepared):
    return [row for row in EventQueue.get_event_history(prepared.uuid)
            if row.phase in (EventPhase.COMPLETION, EventPhase.CANCEL)]


def test_resource_commit_is_once_per_lineage_even_after_recharge(equipped_pack):
    owner, pack = equipped_pack
    prepared = prepare(owner, pack)
    committed = pack.commit_prepared_charge(prepared)
    assert committed.phase is EventPhase.COMPLETION and pack.charges == 0
    pack.on_long_rest(owner.uuid)
    assert pack.charges == 1
    repeated = pack.commit_prepared_charge(prepared)
    assert repeated.uuid == committed.uuid
    assert pack.charges == 1
    assert terminal_versions(prepared) == [committed]


def test_spend_and_recharge_do_not_revive_an_older_preparation(equipped_pack):
    owner, pack = equipped_pack
    stale = prepare(owner, pack)
    other = prepare(owner, pack)
    pack.commit_prepared_charge(other)
    pack.on_long_rest(owner.uuid)
    result = pack.commit_prepared_charge(stale)
    assert result.canceled and pack.charges == 1
    assert len(terminal_versions(stale)) == 1


@pytest.mark.parametrize("interruption", ["admission", "execution", "effect"])
def test_interruption_closes_preparation_without_refunding_completed_work(equipped_pack, interruption):
    owner, pack = equipped_pack
    if interruption == "admission":
        trigger = Trigger(event_type=EventType.ITEM_CHARGE_CONSUMPTION, event_phase=EventPhase.EFFECT)
        def interrupt(event, _):
            owner.unequip_item(BodyPart.BACKPACK)
            return None
    elif interruption == "execution":
        trigger = Trigger(event_type=EventType.CAST_SPELL, event_phase=EventPhase.EXECUTION)
        def interrupt(event, _):
            return event.cancel(status_message="Interrupted before item release")
    else:
        trigger = Trigger(event_type=EventType.CONDITION_APPLICATION, event_phase=EventPhase.DECLARATION)
        def interrupt(event, _):
            return event.cancel(status_message="Effect refused after item release")
    owner.add_event_handler(EventHandler(source_entity_uuid=owner.uuid,
        trigger_conditions=[trigger], event_processor=interrupt))
    use_name = pack.get_use_actions(owner.uuid)[0].get_discovery_template_name()
    result = execute_use_action(owner, pack.uuid, use_name)
    assert result is not None and result.canceled
    assert pack.charges == (0 if interruption == "effect" else 1)
    assert owner.action_economy.actions.normalized_score == (1 if interruption == "admission" else 0)
    declarations = [row for row in EventQueue.get_events_by_type(EventType.ITEM_CHARGE_CONSUMPTION)
                    if row.phase is EventPhase.DECLARATION]
    assert len(declarations) == 1
    terminal, = terminal_versions(declarations[0])
    assert terminal.phase is (EventPhase.COMPLETION if interruption == "effect" else EventPhase.CANCEL)
    assert "Longstrider" not in owner.active_conditions


def test_old_resource_record_defaults_to_consumption_and_recharge_is_explicit(equipped_pack):
    owner, pack = equipped_pack
    completed = pack.commit_prepared_charge(prepare(owner, pack))
    old_payload = encode_event(completed)
    assert old_payload['wire_type'] == 'dnd.blocks.base_item.ItemChargeConsumptionEvent'
    del old_payload['resource_change']
    decoded = decode_event(old_payload)
    assert isinstance(decoded, ItemResourceChangeEvent)
    assert decoded.resource_change is ItemResourceChange.CONSUME
    pack.on_long_rest(owner.uuid)
    recharge = EventQueue.get_events_by_type(EventType.ITEM_CHARGE_CONSUMPTION)[-1]
    restored = decode_event(encode_event(recharge))
    assert isinstance(restored, ItemResourceChangeEvent)
    assert restored.resource_change is ItemResourceChange.RECHARGE
