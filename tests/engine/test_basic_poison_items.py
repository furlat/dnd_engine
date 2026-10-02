"""Basic poison is owned by the weapon and follows normal attacks and transfers."""
from uuid import uuid4

import pytest

from dnd.actions import Attack
from dnd.actions_functional import execute_use_action
from dnd.blocks.base_item import UsableItem
from dnd.blocks.health import HealthConfig
from dnd.content.items.authored_item_builders import build_authored_item
from dnd.core.dice import fixed_dice_faces
from dnd.core.creature_types import DamageType
from dnd.core.equipment_types import WeaponSlot
from dnd.core.events import DamageRollResultEvent, EventPhase, EventQueue, EventType, SavingThrowEvent
from dnd.entity import Entity, EntityConfig
from dnd.game import Game
from dnd.runtime_reset import reset_engine_runtime


@pytest.fixture
def game():
    reset_engine_runtime(grid_size=(8, 5))
    game = Game()
    yield game
    game.close()
    reset_engine_runtime(grid_size=(8, 5))


def actor(game, name, position):
    result = Entity.create(uuid4(), name, config=EntityConfig(faction=name,
        health=HealthConfig(max_hit_points_bonus=200)))
    result.compose_entity()
    game.deploy_entity(result, position)
    return result


def install_poison(owner):
    sword = build_authored_item("weapon.longsword", owner.uuid)
    poison = build_authored_item("consumable.weapon_coat.basic_poison", owner.uuid)
    assert owner.loot_item(sword) and owner.equip_item(sword.uuid, WeaponSlot.MELEE_MAIN)
    assert owner.loot_item(poison)
    before = owner.action_economy.actions.normalized_score
    result = execute_use_action(owner, poison.uuid, "Coat Main Hand")
    assert result is not None and not result.canceled
    assert owner.action_economy.actions.normalized_score == before - 1
    assert not owner.inventory.has_item(poison.uuid)
    assert len(sword.snapshot_item_state().item_effects) == 1
    return sword


def hit(owner, target, faces):
    owner.action_economy.reset_all_costs()
    Entity.update_all_entities_senses()
    with fixed_dice_faces(*faces):
        result = Attack(source_entity_uuid=owner.uuid, target_entity_uuid=target.uuid,
                        weapon_slot=WeaponSlot.MELEE_MAIN).apply()
    assert result is not None and not result.canceled
    roll = EventQueue.get_events_by_type(EventType.DAMAGE_ROLL_RESULT)[-1]
    assert isinstance(roll, DamageRollResultEvent)
    return roll


@pytest.mark.parametrize("faces,poisoned,critical", [
    ((15, 2, 1, 4), True, False),
    ((15, 2, 20), False, False),
    ((20, 2, 2, 1, 4), True, True),
])
def test_poison_save_and_damage_follow_actual_hit(game, faces, poisoned, critical):
    owner = actor(game, "Owner", (1, 1))
    target = actor(game, "Target", (2, 1))
    install_poison(owner)
    roll = hit(owner, target, faces)
    packets = roll.damage_packets
    assert len(packets) == 1 + int(poisoned)
    assert packets[0].damage.dice_numbers == 1
    if poisoned:
        assert packets[1].damage.damage_type is DamageType.POISON
        assert (packets[1].damage.damage_dice, packets[1].damage.dice_numbers) == (4, 1)
        assert packets[1].final_roll.total == 4
    saves = [event for event in EventQueue.get_events_by_type(EventType.SAVING_THROW) if event.phase == EventPhase.COMPLETION]
    assert len(saves) == 1 and isinstance(saves[0], SavingThrowEvent)
    assert saves[0].dc == 10
    assert saves[0].saving_throw_context is not None
    assert not saves[0].saving_throw_context.is_magical
    assert "Poisoned" not in target.active_conditions


def test_poison_miss_does_not_roll_a_save(game):
    owner = actor(game, "Owner", (1, 1))
    target = actor(game, "Target", (2, 1))
    install_poison(owner)
    owner.action_economy.reset_all_costs()
    Entity.update_all_entities_senses()
    hp = target.get_hp()
    with fixed_dice_faces(1):
        result = Attack(source_entity_uuid=owner.uuid, target_entity_uuid=target.uuid, weapon_slot=WeaponSlot.MELEE_MAIN).apply()
    assert result is not None and not result.canceled
    assert target.get_hp() == hp
    assert not EventQueue.get_events_by_type(EventType.SAVING_THROW)


def test_poison_transfers_without_enchanting_another_weapon_and_expires(game):
    owner = actor(game, "Owner", (1, 1))
    recipient = actor(game, "Recipient", (1, 2))
    target = actor(game, "Target", (2, 1))
    sword = install_poison(owner)
    effect = sword.snapshot_item_state().item_effects[0]
    assert owner.unequip_item(WeaponSlot.MELEE_MAIN) is sword
    assert owner.drop_item(sword.uuid) is sword
    assert recipient.loot_item(sword) and recipient.equip_item(sword.uuid, WeaponSlot.MELEE_MAIN)
    assert sword.snapshot_item_state().item_effects[0].effect_uuid == effect.effect_uuid
    ordinary = build_authored_item("weapon.dagger", owner.uuid)
    assert owner.loot_item(ordinary) and owner.equip_item(ordinary.uuid, WeaponSlot.MELEE_MAIN)
    assert len(hit(owner, target, (15, 2)).damage_packets) == 1
    assert not EventQueue.get_events_by_type(EventType.SAVING_THROW)
    assert len(hit(recipient, target, (15, 2, 1, 4)).damage_packets) == 2
    for _ in range(9):
        sword.advance_duration("Basic Poison")
    assert "Basic Poison" in sword.active_conditions
    sword.advance_duration("Basic Poison")
    assert "Basic Poison" not in sword.active_conditions
    assert not sword.snapshot_item_state().item_effects
    count = len(EventQueue.get_events_by_type(EventType.SAVING_THROW))
    assert len(hit(recipient, target, (15, 2)).damage_packets) == 1
    assert len(EventQueue.get_events_by_type(EventType.SAVING_THROW)) == count


def test_poison_does_not_invent_an_object_constitution_save(game):
    owner = actor(game, "Owner", (1, 1))
    install_poison(owner)
    target = build_authored_item("environment.furniture.clay_stove", owner.uuid)
    target.place_on_grid((2, 1))
    owner.action_economy.reset_all_costs()
    Entity.update_all_entities_senses()
    hp = target.get_hp()
    with fixed_dice_faces(15, 2):
        result = Attack(source_entity_uuid=owner.uuid, target_entity_uuid=target.uuid, weapon_slot=WeaponSlot.MELEE_MAIN).apply()
    assert result is not None and not result.canceled
    assert target.get_hp() < hp
    assert not EventQueue.get_events_by_type(EventType.SAVING_THROW)


def test_poison_without_an_action_preserves_the_vial_and_weapon(game):
    owner = actor(game, "Owner", (1, 1))
    sword = build_authored_item("weapon.longsword", owner.uuid)
    poison = build_authored_item("consumable.weapon_coat.basic_poison", owner.uuid)
    assert owner.loot_item(sword) and owner.equip_item(sword.uuid, WeaponSlot.MELEE_MAIN)
    assert owner.loot_item(poison)
    owner.action_economy.consume("actions", 1)
    result = execute_use_action(owner, poison.uuid, "Coat Main Hand")
    assert result is None or result.canceled
    assert owner.inventory.has_item(poison.uuid)
    assert isinstance(poison, UsableItem) and poison.charges == 1
    assert not sword.snapshot_item_state().item_effects


def test_poison_immunity_uses_normal_damage_resolution(game):
    owner = actor(game, "Owner", (1, 1))
    target = Entity.create(uuid4(), "Immune target", config=EntityConfig(faction="target",
        health=HealthConfig(max_hit_points_bonus=200, immunities=[DamageType.POISON])))
    target.compose_entity()
    game.deploy_entity(target, (2, 1))
    install_poison(owner)
    before = target.get_hp()
    roll = hit(owner, target, (15, 2, 1, 4))
    assert len(roll.damage_packets) == 2
    assert target.get_hp() == before - roll.damage_packets[0].final_roll.total


def test_replacing_poison_cleans_the_old_handler(game):
    owner = actor(game, "Owner", (1, 1))
    target = actor(game, "Target", (2, 1))
    sword = install_poison(owner)
    first = sword.snapshot_item_state().item_effects[0].effect_uuid
    owner.action_economy.reset_all_costs()
    vial = build_authored_item("consumable.weapon_coat.basic_poison", owner.uuid)
    assert owner.loot_item(vial)
    applied = execute_use_action(owner, vial.uuid, "Coat Main Hand")
    assert applied is not None and not applied.canceled
    assert len(sword.snapshot_item_state().item_effects) == 1
    assert sword.snapshot_item_state().item_effects[0].effect_uuid != first
    assert len(hit(owner, target, (15, 2, 1, 4)).damage_packets) == 2
    assert len([event for event in EventQueue.get_events_by_type(EventType.SAVING_THROW) if event.phase == EventPhase.COMPLETION]) == 1
