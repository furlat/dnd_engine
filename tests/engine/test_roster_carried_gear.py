"""Ordinary roster possessions reuse equipment, attacks and ownership events."""
from uuid import uuid4
from dataclasses import replace

import pytest

from dnd.actions import Attack
from dnd.blocks.equipment import Weapon
from dnd.content.items.authored_item_builders import build_authored_item, materialize_item_definition
from dnd.content.items.authored_item_definitions import AUTHORED_WEAPON_DEFINITIONS
from dnd.core import dice as dice_module
from dnd.core.equipment_types import BodyPart, WeaponSlot, WeaponProperty
from dnd.core.events import EntityCreatedEvent, EventQueue, EventPhase, EventType, EventHandler, Trigger
from dnd.entity import Entity, EntityConfig
from dnd.game import Game
from dnd.blocks.health import HealthConfig
from dnd.runtime_reset import reset_engine_runtime
from dnd.spells.abjuration import MageArmorCondition


@pytest.fixture
def game():
    reset_engine_runtime(grid_size=(8, 5))
    game = Game()
    yield game
    game.close()
    reset_engine_runtime(grid_size=(8, 5))


def actor(game, name, position):
    entity = Entity.create(uuid4(), name, config=EntityConfig(faction=name,
        health=HealthConfig(max_hit_points_bonus=200)))
    entity.compose_entity()
    game.deploy_entity(entity, position)
    return entity


@pytest.mark.parametrize("item_id,slot", (("focus.wand", WeaponSlot.MELEE_MAIN),
    ("tool.crowbar", WeaponSlot.MELEE_MAIN), ("tool.banner", WeaponSlot.MELEE_MAIN),
    ("weapon.musket", WeaponSlot.RANGED_MAIN)))
def test_carried_gear_uses_normal_attack_and_transfer(game, monkeypatch, item_id, slot):
    owner = actor(game, "Owner", (1, 1))
    recipient = actor(game, "Recipient", (1, 2))
    target = actor(game, "Target", (2, 1))
    item = build_authored_item(item_id, owner.uuid)
    assert owner.loot_item(item) and owner.equip_item(item.uuid, slot)
    Entity.update_all_entities_senses()
    monkeypatch.setattr(dice_module.random, "randint", lambda low, high: min(high, 15))
    hp = target.get_hp()
    result = Attack(source_entity_uuid=owner.uuid, target_entity_uuid=target.uuid, weapon_slot=slot).apply()
    assert result is not None and not result.canceled and target.get_hp() < hp
    assert owner.action_economy.actions.normalized_score == 0
    assert owner.unequip_item(slot) is item and owner.drop_item(item.uuid)
    assert recipient.loot_item(item) and recipient.equip_item(item.uuid, slot)
    assert recipient.equipment.get_weapon(slot) is item


def test_backpack_is_disclosed_at_birth_and_keeps_cloak_slot(game):
    owner = Entity.create(uuid4(), "Owner")
    quiver = build_authored_item("gear.quiver", owner.uuid)
    cloak = build_authored_item("apparel.cloak", owner.uuid)
    owner.install_initial_items(((quiver, BodyPart.BACKPACK), (cloak, BodyPart.CLOAK)))
    owner.compose_entity()
    game.deploy_entity(owner, (1, 1))
    births = [event for _, event in EventQueue.iter_events_since(0)
        if isinstance(event, EntityCreatedEvent) and event.entity_uuid == owner.uuid]
    assert len(births) == 1
    assert (BodyPart.BACKPACK.value, quiver.uuid) in births[0].equipment
    assert (BodyPart.CLOAK.value, cloak.uuid) in births[0].equipment
    assert owner.ac_bonus().normalized_score == 10
    canister = build_authored_item("gear.canister", owner.uuid)
    assert owner.loot_item(canister) and owner.equip_item(canister.uuid, BodyPart.BACKPACK)
    assert owner.inventory.has_item(quiver.uuid)
    assert owner.equipment.backpack is canister and owner.equipment.cloak is cloak
    assert owner.ac_bonus().normalized_score == 10
    assert owner.unequip_item(BodyPart.BACKPACK) is canister
    assert owner.drop_item(canister.uuid)
    recipient = actor(game, "Recipient", (1, 2))
    assert recipient.loot_item(canister) and recipient.equip_item(canister.uuid, BodyPart.BACKPACK)
    assert recipient.equipment.backpack is canister


def test_vetoed_backpack_replacement_keeps_both_items_and_owner(game):
    owner = actor(game, "Owner", (1, 1))
    quiver = build_authored_item("gear.quiver", owner.uuid)
    canister = build_authored_item("gear.canister", owner.uuid)
    assert owner.loot_item(quiver) and owner.equip_item(quiver.uuid, BodyPart.BACKPACK)
    assert owner.loot_item(canister)
    owner.add_event_handler(EventHandler(name="Keep backpack", source_entity_uuid=owner.uuid,
        validation_only=True, event_processor=lambda event, source: event.cancel(status_message="Keep quiver"),
        trigger_conditions=[Trigger(event_type=EventType.ARMOR_UNEQUIP,
            event_phase=EventPhase.EXECUTION, event_source_entity_uuid=owner.uuid)]))
    assert not owner.equip_item(canister.uuid, BodyPart.BACKPACK)
    assert owner.equipment.backpack is quiver and owner.inventory.has_item(canister.uuid)


@pytest.mark.parametrize("item_id", ("weapon.musket", "weapon.longbow"))
def test_two_handed_ranged_weapon_reserves_both_ranged_hands(game, item_id):
    owner = actor(game, "Owner", (1, 1))
    # Author a legal light ranged fixture through the public definition path;
    # the existing spy possession profile does not declare offhand eligibility.
    offhand = materialize_item_definition(replace(
        AUTHORED_WEAPON_DEFINITIONS["weapon.creature.spy_hand_crossbow"],
        item_id="test.light_hand_crossbow", properties=(WeaponProperty.RANGED, WeaponProperty.LIGHT)), owner.uuid)
    main = build_authored_item(item_id, owner.uuid)
    assert isinstance(main, Weapon)
    assert owner.loot_item(offhand) and owner.equip_item(offhand.uuid, WeaponSlot.RANGED_OFF)
    assert owner.loot_item(main) and owner.equip_item(main.uuid, WeaponSlot.RANGED_MAIN)
    assert owner.equipment.weapon_ranged_off is None and owner.inventory.has_item(offhand.uuid)
    assert owner.equip_item(offhand.uuid, WeaponSlot.RANGED_OFF)
    assert owner.equipment.weapon_ranged_main is None and owner.inventory.has_item(main.uuid)


def test_saddle_is_an_ordinary_transferable_inventory_possession(game):
    owner = actor(game, "Owner", (1, 1))
    recipient = actor(game, "Recipient", (1, 2))
    tack = build_authored_item("gear.saddle", owner.uuid)
    assert owner.loot_item(tack) and owner.drop_item(tack.uuid)
    assert recipient.loot_item(tack) and recipient.inventory.has_item(tack.uuid)
    assert not tack.is_equippable and not tack.is_magical


def test_backpack_and_cloak_preserve_mage_armor_but_body_armor_ends_it(game):
    owner = actor(game, "Owner", (1, 1))
    assert owner.add_condition(MageArmorCondition(source_entity_uuid=owner.uuid, target_entity_uuid=owner.uuid))
    ac = owner.ac_bonus().normalized_score
    for item_id, slot in (("gear.quiver", BodyPart.BACKPACK),
                          ("gear.canister", BodyPart.BACKPACK), ("apparel.cloak", BodyPart.CLOAK)):
        item = build_authored_item(item_id, owner.uuid)
        assert owner.loot_item(item) and owner.equip_item(item.uuid, slot)
        assert "Mage Armor" in owner.active_conditions
        assert owner.ac_bonus().normalized_score == ac
    armor = build_authored_item("armor.leather", owner.uuid)
    assert owner.loot_item(armor) and owner.equip_item(armor.uuid, BodyPart.BODY)
    assert "Mage Armor" not in owner.active_conditions
