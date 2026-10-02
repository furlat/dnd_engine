"""Actor-owned hand permission uses normal equipment events and attack budgets."""
from uuid import uuid4

import pytest

from dnd.actions import Attack
from dnd.blocks.equipment import EquipmentConfig, Weapon
from dnd.blocks.base_item import ItemLocationStateEvent
from dnd.blocks.health import HealthConfig
from dnd.content.items.authored_item_builders import build_authored_item
from dnd.core import dice as dice_module
from dnd.core.equipment_types import WeaponSlot
from dnd.core.events import Event, EventHandler, EventPhase, EventQueue, EventType, Trigger, EntityCreatedEvent
from dnd.core.item_types import ItemLocation
from dnd.entity import Entity, EntityConfig
from dnd.game import Game
from dnd.runtime_reset import reset_engine_runtime


@pytest.fixture
def game():
    reset_engine_runtime(grid_size=(6, 5))
    game = Game()
    yield game
    game.close()
    reset_engine_runtime(grid_size=(6, 5))


def actor(game, name, position, grants=()):
    entity = Entity.create(source_entity_uuid=uuid4(), name=name,
        config=EntityConfig(faction=name, health=HealthConfig(max_hit_points_bonus=100),
            equipment=EquipmentConfig(one_handed_offhand_grants=set(grants))))
    entity.compose_entity()
    game.deploy_entity(entity, position)
    return entity


def sword_for(holder):
    sword = build_authored_item("weapon.longsword", holder.uuid)
    assert isinstance(sword, Weapon)
    assert holder.loot_item(sword)
    return sword


def test_talent_changes_suggestions_and_commands_without_changing_sword(game):
    holder = actor(game, "Holder", (1, 1))
    sword = sword_for(holder)
    baseline_slots = sword.compatible_equipment_slots()
    assert "weapon_melee_off" not in holder.equipment.group_equippable_items((sword,))
    with pytest.raises(ValueError, match="LIGHT"):
        holder.equip_item(sword.uuid, WeaponSlot.MELEE_OFF)
    grant = uuid4()
    ac_before = holder.ac_bonus().normalized_score
    holder.grant_one_handed_offhand(grant)
    holder.grant_one_handed_offhand(grant)
    suggestions = holder.equipment.group_equippable_items((sword,))
    assert suggestions["weapon_melee_off"][0]["item_uuid"] == str(sword.uuid)
    assert holder.equip_item(sword.uuid, WeaponSlot.MELEE_OFF)
    assert sword.compatible_equipment_slots() == baseline_slots
    assert holder.ac_bonus().normalized_score == ac_before
    cursor = EventQueue.event_cursor()
    assert holder.revoke_one_handed_offhand(grant)
    assert not holder.revoke_one_handed_offhand(grant)
    assert holder.inventory.has_item(sword.uuid)
    assert holder.equipment.weapon_melee_off is None
    assert any(event.event_type is EventType.WEAPON_UNEQUIP and event.phase is EventPhase.COMPLETION
        for _, event in EventQueue.iter_events_since(cursor))
    assert any(isinstance(event, ItemLocationStateEvent) and event.location is ItemLocation.INVENTORY
        and event.item_state.item_uuid == sword.uuid and event.phase is EventPhase.COMPLETION
        for _, event in EventQueue.iter_events_since(cursor))

    holder.grant_one_handed_offhand(grant)
    assert holder.equip_item(sword.uuid, WeaponSlot.MELEE_OFF)
    assert holder.equipment.weapon_melee_off is sword
    assert holder.revoke_one_handed_offhand(grant)
    assert holder.inventory.has_item(sword.uuid)


def test_birth_permission_and_independent_receipts(game):
    first, second = uuid4(), uuid4()
    holder = Entity.create(source_entity_uuid=uuid4(), name="Holder",
        config=EntityConfig(faction="Holder", equipment=EquipmentConfig(
            one_handed_offhand_grants={first, second})))
    sword = build_authored_item("weapon.longsword", holder.uuid)
    assert isinstance(sword, Weapon)
    holder.install_initial_items(((sword, WeaponSlot.MELEE_OFF),))
    holder.compose_entity()
    game.deploy_entity(holder, (1, 1))
    births = [event for _, event in EventQueue.iter_events_since(0)
        if isinstance(event, EntityCreatedEvent) and event.entity_uuid == holder.uuid]
    assert len(births) == 1
    assert (WeaponSlot.MELEE_OFF.value, sword.uuid) in births[0].equipment
    assert holder.equipment.weapon_melee_off is sword
    assert holder.revoke_one_handed_offhand(first)
    assert holder.equipment.weapon_melee_off is sword
    assert holder.revoke_one_handed_offhand(second)
    assert holder.inventory.has_item(sword.uuid)


@pytest.mark.parametrize("item_id", ("weapon.greatsword", "weapon.longbow"))
def test_talent_does_not_allow_two_handed_or_ranged_weapons_offhand(game, item_id):
    holder = actor(game, "Holder", (1, 1), (uuid4(),))
    weapon = build_authored_item(item_id, holder.uuid)
    assert holder.loot_item(weapon)
    with pytest.raises(ValueError):
        holder.equip_item(weapon.uuid, WeaponSlot.MELEE_OFF)
    assert holder.inventory.has_item(weapon.uuid)


@pytest.mark.parametrize("blocked_by", ("inventory", "event"))
def test_blocked_revocation_retains_talent_and_equipment(game, blocked_by):
    grant = uuid4()
    holder = actor(game, "Holder", (1, 1), (grant,))
    sword = sword_for(holder)
    assert holder.equip_item(sword.uuid, WeaponSlot.MELEE_OFF)
    if blocked_by == "inventory":
        holder.inventory.max_slots = 0
    else:
        holder.add_event_handler(EventHandler(name="Reject unequip", source_entity_uuid=holder.uuid,
            validation_only=True,
            event_processor=lambda event, _source: event.cancel(status_message="Keep sword"),
            trigger_conditions=[Trigger(event_type=EventType.WEAPON_UNEQUIP,
                event_phase=EventPhase.EXECUTION, event_source_entity_uuid=holder.uuid)]))
    budgets = (holder.action_economy.actions.normalized_score, holder.action_economy.bonus_actions.normalized_score)
    assert not holder.revoke_one_handed_offhand(grant)
    assert grant in holder.equipment.one_handed_offhand_grants
    assert holder.equipment.weapon_melee_off is sword
    assert not holder.inventory.has_item(sword.uuid)
    assert (holder.action_economy.actions.normalized_score, holder.action_economy.bonus_actions.normalized_score) == budgets


def test_offhand_can_attack_first_and_does_not_create_extra_actions(game, monkeypatch):
    holder = actor(game, "Holder", (1, 1), (uuid4(),))
    target = actor(game, "Target", (2, 1))
    sword = sword_for(holder)
    axe = build_authored_item("weapon.handaxe", holder.uuid)
    assert holder.equip_item(sword.uuid, WeaponSlot.MELEE_OFF)
    assert holder.loot_item(axe) and holder.equip_item(axe.uuid, WeaponSlot.MELEE_MAIN)
    Entity.update_all_entities_senses()
    monkeypatch.setattr(dice_module.random, "randint", lambda low, high: min(high, 15))
    for slot in (WeaponSlot.MELEE_OFF, WeaponSlot.MELEE_MAIN):
        event = Attack(source_entity_uuid=holder.uuid, target_entity_uuid=target.uuid, weapon_slot=slot).apply()
        assert event is not None and not event.canceled
    assert holder.action_economy.actions.normalized_score == 0
    assert holder.action_economy.bonus_actions.normalized_score == 0
    event = Attack(source_entity_uuid=holder.uuid, target_entity_uuid=target.uuid, weapon_slot=WeaponSlot.MELEE_OFF).apply()
    assert event is None or event.canceled


def test_execution_rechecks_weapon_after_talent_revocation(game):
    grant = uuid4()
    holder = actor(game, "Holder", (1, 1), (grant,))
    target = actor(game, "Target", (2, 1))
    sword = sword_for(holder)
    assert holder.equip_item(sword.uuid, WeaponSlot.MELEE_OFF)
    Entity.update_all_entities_senses()

    def revoke(event: Event, _source):
        assert holder.revoke_one_handed_offhand(grant)
        return event

    holder.add_event_handler(EventHandler(name="Lose talent during attack", source_entity_uuid=holder.uuid,
        event_processor=revoke, trigger_conditions=[Trigger(event_type=EventType.ATTACK,
            event_phase=EventPhase.EXECUTION, event_source_entity_uuid=holder.uuid)]))
    hp_before = target.get_hp()
    result = Attack(source_entity_uuid=holder.uuid, target_entity_uuid=target.uuid,
        weapon_slot=WeaponSlot.MELEE_OFF).apply()
    assert result is not None and result.canceled
    assert target.get_hp() == hp_before
    assert holder.inventory.has_item(sword.uuid)
    # Execution interruption happens after the original bonus-action cost.
    assert holder.action_economy.bonus_actions.normalized_score == 0
    assert holder.action_economy.actions.normalized_score == 1
