"""Assassin poison uses real doses, coated weapons and normal damage defenses."""

from uuid import uuid4

import pytest

from dnd.actions import Attack, AttackEvent
from dnd.actions_functional import execute_use_action, setup_standard_actions
from dnd.blocks.base_item import UsableItem
from dnd.blocks.health import HealthConfig
from dnd.content.items.authored_item_builders import build_authored_item
from dnd.core.dice import AttackOutcome, fixed_dice_faces
from dnd.core.creature_types import DamageType
from dnd.core.equipment_types import WeaponSlot
from dnd.core.events import DamageRollResultEvent, EventHandler, EventPhase, EventQueue, EventType, SavingThrowEvent, Trigger
from dnd.entity import Entity, EntityConfig
from dnd.game import Game
from dnd.runtime_reset import reset_engine_runtime


@pytest.fixture
def game():
    reset_engine_runtime(grid_size=(10, 6))
    result = Game()
    yield result
    result.close()
    reset_engine_runtime(grid_size=(10, 6))


def actor(game, name, position, *, resistance=False, immunity=False):
    creature = Entity.create(uuid4(), name, config=EntityConfig(
        faction=name,
        health=HealthConfig(max_hit_points_bonus=200,
            resistances=[DamageType.POISON] if resistance else [],
            immunities=[DamageType.POISON] if immunity else []),
    ))
    creature.compose_entity()
    setup_standard_actions(creature)
    game.deploy_entity(creature, position)
    return creature


def coat(owner):
    sword = build_authored_item("weapon.longsword", owner.uuid)
    vial = build_authored_item("consumable.weapon_coat.assassin_poison", owner.uuid)
    assert isinstance(vial, UsableItem)
    assert owner.loot_item(sword) and owner.equip_item(sword.uuid, WeaponSlot.MELEE_MAIN)
    assert owner.loot_item(vial)
    result = execute_use_action(owner, vial.uuid, "Coat Main Hand")
    assert result is not None and not result.canceled
    assert not owner.inventory.has_item(vial.uuid)
    assert vial.charges == 0
    return sword


def strike(owner, target, faces, *, slot=WeaponSlot.MELEE_MAIN):
    owner.action_economy.reset_all_costs()
    Entity.update_all_entities_senses(max_distance=100)
    template = next(row for row in owner.registered_actions
                    if isinstance(row, Attack) and row.weapon_slot is slot)
    attack = template.instantiate(target_entity_uuid=target.uuid)
    with fixed_dice_faces(*faces):
        result = owner.perform(attack, attack.current_selection())
    assert isinstance(result, AttackEvent) and not result.canceled
    return result


@pytest.mark.parametrize("saved,critical", [(False, False), (True, False), (False, True), (True, True)])
def test_assassin_poison_hit_profile_is_separately_saved_and_never_crit_doubled(game, saved, critical):
    owner = actor(game, "Owner", (1, 1))
    target = actor(game, "Target", (2, 1))
    coat(owner)
    hp = target.get_normal_hp()
    faces = [20 if critical else 15, *([2] * (2 if critical else 1)),
             20 if saved else 1, *([3] * 7)]

    event = strike(owner, target, faces)

    assert event.attack_outcome is (AttackOutcome.CRIT if critical else AttackOutcome.HIT)
    assert event.damages is not None and event.damage_rolls is not None
    assert len(event.damages) == 2
    poison = event.damages[1]
    assert (poison.damage_type, poison.dice_numbers, poison.damage_dice) == (DamageType.POISON, 7, 6)
    assert event.damage_rolls[1].effective_dice_count == 7
    assert event.damage_rolls[1].total == (10 if saved else 21)
    recorded = next(row for row in reversed(EventQueue.get_events_by_type(EventType.DAMAGE_ROLL_RESULT))
                    if row.phase is EventPhase.COMPLETION)
    assert isinstance(recorded, DamageRollResultEvent)
    assert recorded.damage_packets[1].original_roll.total == 21
    assert recorded.damage_packets[1].final_roll.total == (10 if saved else 21)
    assert target.get_normal_hp() == hp - event.damage_rolls[0].total - (10 if saved else 21)
    saves = [row for row in EventQueue.get_events_by_type(EventType.SAVING_THROW)
             if row.phase is EventPhase.COMPLETION]
    assert len(saves) == 1 and isinstance(saves[0], SavingThrowEvent)
    assert saves[0].dc == 15 and saves[0].ability_name == "constitution"
    assert saves[0].result is saved
    assert saves[0].saving_throw_context is not None and not saves[0].saving_throw_context.is_magical
    assert "Poisoned" not in target.active_conditions


@pytest.mark.parametrize("saved,resistance,immunity,expected_poison", [
    (False, True, False, 10), (True, True, False, 5),
    (False, False, True, 0), (True, False, True, 0),
])
def test_assassin_poison_composes_with_normal_damage_affinities(game, saved, resistance, immunity, expected_poison):
    owner = actor(game, "Owner", (1, 1))
    target = actor(game, "Target", (2, 1), resistance=resistance, immunity=immunity)
    coat(owner)
    before = target.get_normal_hp()

    event = strike(owner, target, [15, 2, 20 if saved else 1, *([3] * 7)])

    assert target.get_normal_hp() == before - event.damage_rolls[0].total - expected_poison


def test_assassin_poison_misses_never_request_a_save(game):
    owner = actor(game, "Owner", (1, 1))
    target = actor(game, "Target", (2, 1))
    coat(owner)
    hp = target.get_normal_hp()

    assert strike(owner, target, [1]).attack_outcome is AttackOutcome.CRIT_MISS
    assert target.get_normal_hp() == hp
    assert not EventQueue.get_events_by_type(EventType.SAVING_THROW)


def test_only_the_attacking_coated_item_dispatches_even_after_transfer(game):
    owner = actor(game, "Owner", (1, 1))
    recipient = actor(game, "Recipient", (1, 3))
    target = actor(game, "Target", (2, 2))
    sword = coat(owner)
    coat(recipient)
    dispatches = []
    EventQueue.add_on_handler_dispatch_callback(dispatches.append)
    try:
        strike(owner, target, [15, 2, 1, *([3] * 7)])
        poison_dispatches = [row for row in dispatches if row.handler_name == "Assassin Poison"]
        assert [row.source_entity_uuid for row in poison_dispatches] == [str(sword.uuid)]
        dispatches.clear()

        assert owner.unequip_item(WeaponSlot.MELEE_MAIN) is sword
        assert owner.drop_item(sword.uuid) is sword
        assert recipient.loot_item(sword) and recipient.equip_item(sword.uuid, WeaponSlot.MELEE_MAIN)
        dagger = build_authored_item("weapon.dagger", owner.uuid)
        assert owner.loot_item(dagger) and owner.equip_item(dagger.uuid, WeaponSlot.MELEE_MAIN)

        assert len(strike(owner, target, [15, 2]).damages) == 1
        assert not [row for row in dispatches if row.handler_name == "Assassin Poison"]
        strike(recipient, target, [15, 2, 1, *([3] * 7)])
        poison_dispatches = [row for row in dispatches if row.handler_name == "Assassin Poison"]
        assert [row.source_entity_uuid for row in poison_dispatches] == [str(sword.uuid)]
        dispatches.clear()

        sword.remove_condition("Assassin Poison")
        assert len(strike(recipient, target, [15, 2]).damages) == 1
        assert not [row for row in dispatches if row.handler_name == "Assassin Poison"]
    finally:
        EventQueue.remove_on_handler_dispatch_callback(dispatches.append)


def test_assassin_poison_follows_its_authored_coating_duration(game):
    owner = actor(game, "Owner", (1, 1))
    target = actor(game, "Target", (2, 1))
    sword = coat(owner)
    remaining = sword.active_conditions["Assassin Poison"].duration.duration
    assert remaining is not None and remaining > 0
    for _ in range(remaining - 1):
        sword.advance_duration("Assassin Poison")
    assert sword.snapshot_item_state().item_effects
    sword.advance_duration("Assassin Poison")

    assert not sword.snapshot_item_state().item_effects
    assert len(strike(owner, target, [15, 2]).damages) == 1
    assert not EventQueue.get_events_by_type(EventType.SAVING_THROW)


@pytest.mark.parametrize("refusal", ["no_action", "no_weapon", "condition", "action_effect"])
def test_assassin_poison_refusal_never_installs_an_effect(game, refusal):
    owner = actor(game, "Owner", (1, 1))
    sword = build_authored_item("weapon.longsword", owner.uuid)
    vial = build_authored_item("consumable.weapon_coat.assassin_poison", owner.uuid)
    assert owner.loot_item(sword) and owner.loot_item(vial)
    if refusal != "no_weapon":
        assert owner.equip_item(sword.uuid, WeaponSlot.MELEE_MAIN)
    if refusal == "no_action":
        owner.action_economy.consume("actions", 1)
    if refusal in {"condition", "action_effect"}:
        owner.add_event_handler(EventHandler(
            name="Refuse poison application",
            source_entity_uuid=owner.uuid,
            trigger_conditions=[Trigger(
                event_type=EventType.CONDITION_APPLICATION if refusal == "condition" else EventType.BASE_ACTION,
                event_phase=EventPhase.DECLARATION if refusal == "condition" else EventPhase.EFFECT,
                event_target_entity_uuid=sword.uuid if refusal == "condition" else owner.uuid,
            )],
            event_processor=lambda event, _: event.cancel(status_message="Poison application refused"),
        ))

    result = execute_use_action(owner, vial.uuid, "Coat Main Hand")

    assert result is None or result.canceled
    assert not sword.snapshot_item_state().item_effects
    if refusal in {"no_action", "no_weapon"}:
        assert owner.inventory.has_item(vial.uuid) and vial.charges == 1


def test_assassin_poison_does_not_request_constitution_saves_from_objects(game):
    owner = actor(game, "Owner", (1, 1))
    coat(owner)
    target = build_authored_item("environment.furniture.clay_stove", owner.uuid)
    target.place_on_grid((2, 1))

    event = strike(owner, target, [15, 2])

    assert len(event.damages) == 1
    assert not EventQueue.get_events_by_type(EventType.SAVING_THROW)


def test_assassin_poison_coats_the_actual_crossbow_without_an_ammunition_model(game):
    owner = actor(game, "Owner", (1, 1))
    target = actor(game, "Target", (5, 1))
    crossbow = build_authored_item("weapon.light_crossbow", owner.uuid)
    vial = build_authored_item("consumable.weapon_coat.assassin_poison", owner.uuid)
    assert owner.loot_item(crossbow) and owner.equip_item(crossbow.uuid, WeaponSlot.RANGED_MAIN)
    assert owner.loot_item(vial)
    result = execute_use_action(owner, vial.uuid, "Coat Ranged Main Hand")
    assert result is not None and not result.canceled

    event = strike(owner, target, [15, 2, 1, *([3] * 7)], slot=WeaponSlot.RANGED_MAIN)

    assert event.source_item_uuid == crossbow.uuid
    assert len(event.damages) == 2 and event.damage_rolls[1].total == 21
