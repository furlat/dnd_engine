"""Roster psychic power belongs to the physical weapon through real attacks/loot."""
from uuid import uuid4

import pytest

from dnd.actions import Attack
from dnd.blocks.health import HealthConfig
from dnd.blocks.equipment import Weapon
from dnd.content.items.authored_item_builders import build_authored_item
from dnd.content.items.roster_item_definitions import ROSTER_MAUL_DEFINITION, ROSTER_WEAPON_DEFINITIONS, ROSTER_EMBER_DEFINITIONS
from dnd.core import dice as dice_module
from dnd.core.creature_types import DamageType
from dnd.core.equipment_types import WeaponSlot
from dnd.core.events import DamageRollResultEvent, EventQueue, EventType
from dnd.entity import Entity, EntityConfig
from dnd.game import Game
from dnd.runtime_reset import reset_engine_runtime


@pytest.fixture(autouse=True)
def fresh_runtime():
    reset_engine_runtime(grid_size=(6, 5))
    yield
    reset_engine_runtime(grid_size=(6, 5))


@pytest.fixture
def game():
    game = Game()
    yield game
    game.close()


def actor(game, name, position):
    entity = Entity.create(source_entity_uuid=uuid4(), name=name,
        config=EntityConfig(faction=name, health=HealthConfig(max_hit_points_bonus=500)))
    entity.compose_entity()
    game.deploy_entity(entity, position)
    return entity


@pytest.mark.parametrize("item_id", tuple({**ROSTER_WEAPON_DEFINITIONS, **ROSTER_EMBER_DEFINITIONS}))
def test_psychic_weapon_hits_transfer_and_do_not_enchant_another_weapon(item_id, monkeypatch, game):
    first = actor(game, "First", (1, 1))
    recipient = actor(game, "Recipient", (1, 2))
    target = actor(game, "Target", (2, 1))
    definition = {**ROSTER_WEAPON_DEFINITIONS, **ROSTER_EMBER_DEFINITIONS}[item_id]
    item = build_authored_item(item_id, first.uuid)
    assert isinstance(item, Weapon)
    assert first.loot_item(item) and first.equip_item(item.uuid, WeaponSlot.MELEE_MAIN)
    Entity.update_all_entities_senses()
    # Deterministic successful non-critical hit; rider dice still roll normally.
    monkeypatch.setattr(dice_module.random, "randint", lambda low, high: min(high, 15))
    expected = definition.additional_damage[0]
    item_uuid = item.uuid
    for holder in (first, recipient):
        damage_before = target.health.damage_taken
        result = Attack(source_entity_uuid=holder.uuid, target_entity_uuid=target.uuid,
            weapon_slot=WeaponSlot.MELEE_MAIN).apply()
        assert result is not None and not result.canceled
        roll = EventQueue.get_events_by_type(EventType.DAMAGE_ROLL_RESULT)[-1]
        assert isinstance(roll, DamageRollResultEvent)
        packets = roll.damage_packets
        assert [packet.damage.damage_type for packet in packets] == [definition.damage_type, expected.damage_type]
        assert packets[1].damage.dice_numbers == expected.count
        assert target.health.damage_taken - damage_before == sum(packet.final_roll.total for packet in packets)
        assert item.is_magical
        assert item.attack_bonus.normalized_score == definition.attack_bonus
        assert item.damage_bonus is not None
        assert item.damage_bonus.normalized_score == definition.damage_bonus
        assert item.uuid == item_uuid
        if holder is first:
            assert first.unequip_item(WeaponSlot.MELEE_MAIN) is item
            assert first.drop_item(item.uuid) is item
            assert recipient.loot_item(item)
            assert recipient.equip_item(item.uuid, WeaponSlot.MELEE_MAIN)
    # Item bonuses and psychic packets did not leak into the original holder.
    ordinary = build_authored_item("weapon.dagger", first.uuid)
    assert first.loot_item(ordinary) and first.equip_item(ordinary.uuid, WeaponSlot.MELEE_OFF)
    result = Attack(source_entity_uuid=first.uuid, target_entity_uuid=target.uuid,
        weapon_slot=WeaponSlot.MELEE_OFF).apply()
    assert result is not None and not result.canceled
    roll = EventQueue.get_events_by_type(EventType.DAMAGE_ROLL_RESULT)[-1]
    assert isinstance(roll, DamageRollResultEvent)
    packets = roll.damage_packets
    assert [packet.damage.damage_type for packet in packets] == [DamageType.PIERCING]


def test_maul_uses_two_hands_and_normal_bludgeoning_attack(monkeypatch, game):
    holder = actor(game, "Holder", (1, 1))
    target = actor(game, "Target", (2, 1))
    shield = build_authored_item("shield.shield", holder.uuid)
    maul = build_authored_item(ROSTER_MAUL_DEFINITION.item_id, holder.uuid)
    assert holder.loot_item(shield) and holder.equip_item(shield.uuid, WeaponSlot.MELEE_OFF)
    assert holder.loot_item(maul) and holder.equip_item(maul.uuid, WeaponSlot.MELEE_MAIN)
    assert holder.equipment.weapon_melee_off is None
    assert holder.inventory.has_item(shield.uuid)
    Entity.update_all_entities_senses()
    monkeypatch.setattr(dice_module.random, "randint", lambda low, high: min(high, 15))
    damage_before = target.health.damage_taken
    result = Attack(source_entity_uuid=holder.uuid, target_entity_uuid=target.uuid,
        weapon_slot=WeaponSlot.MELEE_MAIN).apply()
    assert result is not None and not result.canceled
    roll = EventQueue.get_events_by_type(EventType.DAMAGE_ROLL_RESULT)[-1]
    assert isinstance(roll, DamageRollResultEvent)
    assert len(roll.damage_packets) == 1
    damage = roll.damage_packets[0].damage
    assert damage.damage_type is DamageType.BLUDGEONING
    assert (damage.dice_numbers, damage.damage_dice) == (2, 6)
    assert target.health.damage_taken - damage_before == roll.damage_packets[0].final_roll.total
