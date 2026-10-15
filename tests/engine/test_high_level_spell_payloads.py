"""Native retained-source spheres, paid delivery, transfer and terminal blasts."""

import pytest

from dnd.actions import PickUp
from dnd.blocks.base_item import BaseItem
from dnd.core.base_block import BaseBlock
from dnd.core.base_conditions import ConditionApplicationEvent, ConditionRemovalEvent
from dnd.core.creature_types import DamageType
from dnd.core.dice import fixed_dice_faces
from dnd.core.events import EventHandler, EventPhase, EventQueue, EventType, Trigger
from dnd.core.gridmap import get_map
from dnd.entity import Entity
from dnd.items.spell_payloads import (
    SpellPayloadItem,
    SpellPayloadLifetime,
    ThrowSpellPayload,
    TouchDelayedFireball,
)
from dnd.spells.abjuration import AntimagicField
from dnd.spells.evocation import DelayedBlastFireball, FreezingSphere
from dnd.spells.wall_constructions import WallOfForce
from tests.engine.test_high_level_spell_controls import (
    cast,
    conditions,
    game,
    high_actor,
)
from tests.manual.spell_regression_support import force_save_result


def payload(actor):
    return next(
        item
        for item in actor.inventory.items.values()
        if isinstance(item, SpellPayloadItem)
    )


def test_freezing_launch_con_half_and_real_ice(game):
    caster = high_actor(game)
    victim = high_actor(game, "Victim", (8, 2), "foes")
    force_save_result(victim, "constitution", succeeds=True)
    hp = victim.get_hp()
    with fixed_dice_faces(*([2] * 100)):
        cast(FreezingSphere, caster, end_position=victim.position)
    assert victim.get_hp() == hp - 10
    assert any(
        victim.position in zone.affected_positions and zone.name == "Ice Surface"
        for zone in get_map().get_spatial_conditions()
    )


def test_portable_freezing_transfer_then_throw_retains_power_and_retires_once(game):
    caster = high_actor(game)
    holder = high_actor(game, "Holder", (3, 2))
    victim = high_actor(game, "Victim", (10, 2), "foes")
    force_save_result(victim, "constitution", succeeds=False)
    cast(FreezingSphere, caster, holder, delivery="portable")
    item = payload(holder)
    assert item.original_caster_uuid == caster.uuid and item.dice_count == 10
    hp = victim.get_hp()
    throw = next(
        action
        for action in item.get_use_actions(holder.uuid)
        if isinstance(action, ThrowSpellPayload)
    )
    with fixed_dice_faces(*([2] * 100)):
        result = throw.instantiate(end_position=victim.position).apply()
    assert result is not None and not result.canceled, (
        result.status_message if result else "No action"
    )
    assert victim.get_hp() == hp - 20
    assert BaseBlock.get(item.uuid) is None
    assert not any(
        isinstance(effect, SpellPayloadLifetime)
        for effect in caster.active_conditions_by_uuid.values()
    )
    with fixed_dice_faces(*([2] * 100)):
        caster.on_turn_end()
    assert victim.get_hp() == hp - 20


@pytest.mark.parametrize("destination", [(17, 7), (80, 80)])
def test_invalid_payload_throw_keeps_item_and_cost(game, destination):
    caster = high_actor(game)
    cast(FreezingSphere, caster, caster, delivery="portable")
    item = payload(caster)
    caster.action_economy.reset_all_costs()
    throw = next(
        action
        for action in item.get_use_actions(caster.uuid)
        if isinstance(action, ThrowSpellPayload)
    )
    result = throw.instantiate(end_position=destination).apply()
    assert result is not None and result.canceled
    assert (
        BaseBlock.get(item.uuid) is item
        and caster.action_economy.actions.normalized_score == 1
    )


def test_delayed_bead_growth_concentration_release_and_floor_throw_cannot_bypass_touch(
    game,
):
    caster = high_actor(game)
    toucher = high_actor(game, "Toucher", (8, 3))
    victim = high_actor(game, "Victim", (9, 2), "foes")
    force_save_result(victim, "dexterity", succeeds=False)
    cast(DelayedBlastFireball, caster, end_position=(8, 2))
    item = next(
        item for item in BaseItem.get_all_items() if isinstance(item, SpellPayloadItem)
    )
    assert item.dice_count == 12 and get_map().get_object_position(item.uuid) == (8, 2)
    caster.on_turn_end()
    assert item.dice_count == 13
    direct = ThrowSpellPayload(
        source_entity_uuid=toucher.uuid,
        source_item_uuid=item.uuid,
        end_position=(12, 2),
    ).apply()
    assert (
        direct is not None
        and direct.canceled
        and toucher.action_economy.actions.normalized_score == 1
    )
    hp = victim.get_hp()
    with fixed_dice_faces(*([2] * 200)):
        caster.remove_condition("Concentrating")
    assert victim.get_hp() == hp - 26 and BaseBlock.get(item.uuid) is None


@pytest.mark.parametrize("success,throw", [(False, False), (True, False), (True, True)])
def test_delayed_touch_pays_action_and_pickup_or_throw_obeys_save(game, success, throw):
    caster = high_actor(game)
    holder = high_actor(game, "Holder", (8, 3))
    victim = high_actor(game, "Victim", (11, 2), "foes")
    force_save_result(holder, "dexterity", succeeds=success)
    force_save_result(victim, "dexterity", succeeds=False)
    cast(DelayedBlastFireball, caster, end_position=(8, 2))
    item = next(
        item for item in BaseItem.get_all_items() if isinstance(item, SpellPayloadItem)
    )
    pickup = PickUp(
        source_entity_uuid=holder.uuid, target_entity_uuid=item.uuid
    ).apply()
    assert pickup is not None and pickup.canceled
    hp = victim.get_hp()
    with fixed_dice_faces(*([2] * 200)):
        result = TouchDelayedFireball(
            source_entity_uuid=holder.uuid,
            source_item_uuid=item.uuid,
            throw_after_touch=throw,
            target_type="position_los" if throw else "self",
            end_position=victim.position if throw else None,
        ).apply()
    assert result is not None and not result.canceled, (
        result.status_message if result else "No result"
    )
    assert holder.action_economy.actions.normalized_score == 0
    if success and not throw:
        assert item.owner_uuid == holder.uuid and BaseBlock.get(item.uuid) is item
        assert victim.get_hp() == hp
    else:
        assert BaseBlock.get(item.uuid) is None and victim.get_hp() < hp


def test_payload_deadline_veto_caps_growth_and_later_retires_once(game):
    caster = high_actor(game)
    victim = high_actor(game, "Victim", (10, 2), "foes")
    force_save_result(victim, "dexterity", succeeds=False)
    cast(DelayedBlastFireball, caster, end_position=(8, 2))
    item = next(
        item for item in BaseItem.get_all_items() if isinstance(item, SpellPayloadItem)
    )

    def veto(event, _):
        if isinstance(event, ConditionRemovalEvent) and isinstance(
            event.condition, SpellPayloadLifetime
        ):
            return event.cancel(status_message="Ending refused")
        return None

    handler = EventHandler(
        name="Payload ending veto",
        source_entity_uuid=caster.uuid,
        trigger_conditions=[
            Trigger(
                event_type=EventType.CONDITION_REMOVAL, event_phase=EventPhase.EFFECT
            )
        ],
        event_processor=veto,
    )
    caster.add_event_handler(handler)
    for _ in range(11):
        caster.on_turn_end()
    assert item.dice_count == 22 and BaseBlock.get(item.uuid) is item
    caster.remove_event_handler(handler)
    hp = victim.get_hp()
    with fixed_dice_faces(*([2] * 300)):
        caster.on_turn_end()
    assert BaseBlock.get(item.uuid) is None and victim.get_hp() == hp - 44
    hp = victim.get_hp()
    caster.on_turn_end()
    assert victim.get_hp() == hp


def test_freezing_throw_owner_removal_veto_preserves_item_and_payload(game):
    caster = high_actor(game)
    victim = high_actor(game, "Victim", (8, 2), "foes")
    cast(FreezingSphere, caster, caster, delivery="portable")
    item = payload(caster)
    caster.action_economy.reset_all_costs()

    def veto(event, _):
        if isinstance(event, ConditionRemovalEvent) and isinstance(
            event.condition, SpellPayloadLifetime
        ):
            return event.cancel(status_message="No ending")
        return None

    handler = EventHandler(
        name="Ending veto",
        source_entity_uuid=caster.uuid,
        trigger_conditions=[
            Trigger(
                event_type=EventType.CONDITION_REMOVAL, event_phase=EventPhase.EFFECT
            )
        ],
        event_processor=veto,
    )
    caster.add_event_handler(handler)
    hp = victim.get_hp()
    result = ThrowSpellPayload(
        source_entity_uuid=caster.uuid,
        source_item_uuid=item.uuid,
        end_position=victim.position,
    ).apply()
    assert result is not None and result.canceled
    assert (
        BaseBlock.get(item.uuid) is item
        and item.owner_uuid == caster.uuid
        and victim.get_hp() == hp
    )
    caster.remove_event_handler(handler)


def test_world_close_retires_spell_payload_without_gameplay_blast(game):
    caster = high_actor(game)
    victim = high_actor(game, "Victim", (8, 2), "foes")
    cast(DelayedBlastFireball, caster, end_position=(8, 2))
    item = next(
        item for item in BaseItem.get_all_items() if isinstance(item, SpellPayloadItem)
    )
    hp = victim.get_hp()
    game.close()
    assert BaseBlock.get(item.uuid) is None and victim.get_hp() == hp


def test_freezing_blast_before_force_wall_cannot_harm_or_ice_far_side(game):
    caster = high_actor(game)
    wall_caster = high_actor(game, "Wall caster", (3, 6))
    victim = high_actor(game, "Victim", (10, 2), "foes")
    cast(WallOfForce, wall_caster, end_position=(8, 1), extra_target_positions=[(8, 7)])
    hp = victim.get_hp()
    with fixed_dice_faces(*([2] * 300)):
        cast(FreezingSphere, caster, end_position=(7, 2))
    assert victim.get_hp() == hp
    assert not any(
        victim.position in zone.affected_positions and zone.name == "Ice Surface"
        for zone in get_map().get_spatial_conditions()
    )


@pytest.mark.parametrize("kind", [FreezingSphere, DelayedBlastFireball])
def test_suppressed_payload_deadline_consumes_without_deferred_blast(game, kind):
    caster = high_actor(game)
    holder = high_actor(game, "Holder", (8, 2))
    victim = high_actor(game, "Victim", (9, 2), "foes")
    suppressor = high_actor(game, "Suppressor", (8, 3), "others")
    if kind is FreezingSphere:
        # Create in hand reach, then move the holder into the suppression area.
        holder.move((3, 2))
        cast(kind, caster, holder, delivery="portable")
        item = payload(holder)
        holder.move((8, 2))
    else:
        cast(kind, caster, end_position=holder.position)
        item = next(
            item
            for item in BaseItem.get_all_items()
            if isinstance(item, SpellPayloadItem)
        )
    cast(AntimagicField, suppressor)
    hp = victim.get_hp()
    for _ in range(10):
        caster.on_turn_end()
    assert BaseBlock.get(item.uuid) is None and victim.get_hp() == hp
    suppressor.remove_condition("Concentrating")
    caster.on_turn_end()
    assert victim.get_hp() == hp


@pytest.mark.parametrize("ending", ["destruction", "rest", "caster_death"])
def test_portable_gameplay_ending_explodes_once_at_holder_position(game, ending):
    caster = high_actor(game)
    holder = high_actor(game, "Holder", (3, 2))
    victim = high_actor(game, "Victim", (8, 2), "foes")
    force_save_result(victim, "constitution", succeeds=False)
    cast(FreezingSphere, caster, holder, delivery="portable")
    item = payload(holder)
    holder.move((8, 3))
    hp = victim.get_hp()
    with fixed_dice_faces(*([2] * 400)):
        if ending == "destruction":
            item.receive_damage(10, DamageType.FORCE, caster.uuid)
        elif ending == "rest":
            caster.on_long_rest()
        else:
            caster.receive_damage(1000, DamageType.FORCE, victim.uuid)
    assert BaseBlock.get(item.uuid) is None and victim.get_hp() == hp - 20
    hp = victim.get_hp()
    caster.on_turn_end()
    assert victim.get_hp() == hp
