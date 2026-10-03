"""Terminal actor release preserves real possessions and removes exact live authority.

Boundary: Game's prepared native retirement (the summoning owner removes its
existence condition before commit). Inputs: explicit terminal cause, carried
items and vetoes. Outputs: world/ownership state and causal retained facts.
"""
from uuid import uuid4

import pytest

from dnd.actions import Attack
from dnd.actions_functional import execute_use_action
from dnd.blocks.base_item import BaseItem, ItemLocationStateEvent
from dnd.conditions import Blinded
from dnd.content.items.authored_item_builders import build_authored_item
from dnd.content_system.creature_materialization import materialize_creature
from dnd.core.base_block import BaseBlock
from dnd.core.base_conditions import ConditionRemovalEvent
from dnd.core.base_object import BaseObject
from dnd.core.equipment_types import WeaponSlot, BodyPart
from dnd.core.content.materialization import CreatureDeploymentRole, CreaturePossessionMode
from dnd.core.creature_types import DamageType
from dnd.core.events import Event, EventHandler, EventPhase, EventQueue, EventType, Trigger
from dnd.core.gridmap import get_map
from dnd.core.item_types import ItemLocation
from dnd.core.values import BaseValue, ModifiableValue
from dnd.entity import Entity
from dnd.game import Game
from dnd.items.consumables import build_timed_fire_weapon_coat
from dnd.items.environment_interactables import StorageChest
from dnd.monsters.srd_roster import SRD_CREATURE_RECIPES_BY_ID
from dnd.runtime_reset import reset_engine_runtime
from dnd.types.summoning import SummonDepartureCause, TerminalOwnerRelease


@pytest.fixture(autouse=True)
def reset():
    reset_engine_runtime(grid_size=(6, 5))
    yield
    reset_engine_runtime()


def actor(game, name='Departing', position=(2, 2)):
    entity = Entity.create(source_entity_uuid=uuid4(), name=name)
    entity.compose_entity()
    game.deploy_entity(entity, position)
    return entity


def release(game, entity, cause=SummonDepartureCause.EXPIRED, parent=None):
    return game.prepare_entity_retirement(entity.uuid, cause=TerminalOwnerRelease(
        entity_uuid=entity.uuid, existence_condition_uuid=uuid4(), cause=cause,
        parent_event_uuid=parent.uuid if parent is not None else None), parent_event=parent)


def give(entity, identity, slot=None):
    item = build_authored_item(identity, entity.uuid)
    assert entity.loot_item(item)
    if slot is not None:
        assert entity.equip_item(item.uuid, slot)
    return item


def value_identities(value):
    channels = (value.self_static, value.self_contextual, value.to_target_static, value.to_target_contextual)
    return {value.uuid, *(channel.uuid for channel in channels),
            *(identity for channel in channels for identity in channel.get_all_modifier_uuids())}


def still_registered(identity):
    return any(owner.get(identity) is not None for owner in (BaseBlock, BaseValue, BaseObject))


def test_canonical_creature_retirement_releases_hit_dice_and_owned_bonus_lists_only():
    game = Game()
    entity = materialize_creature(SRD_CREATURE_RECIPES_BY_ID['wolf'], runtime_entity_uuid=uuid4(),
        display_name='Wolf', faction='allies', position=(2, 2),
        deployment_role=CreatureDeploymentRole(role_id='test.retirement'),
        possession_mode=CreaturePossessionMode.INCLUDE_DEFAULT_POSSESSIONS)
    entity.compose_entity()
    game.deploy_entity(entity, (2, 2))
    hit_dice = tuple(entity.health.hit_dices)
    assert hit_dice
    removed = {die.uuid for die in hit_dice}
    for die in hit_dice:
        removed.update(value_identities(die.hit_dice_value))
        removed.update(value_identities(die.hit_dice_count))
    bite = entity.equipment.get_weapon(WeaponSlot.MELEE_MAIN)
    assert bite is not None and bite.intrinsic_owner_uuid == entity.uuid
    bonuses = [ModifiableValue.create(source_entity_uuid=entity.uuid, base_value=2, value_name=name)
               for name in ('Body damage', 'Attack damage', 'Spell damage')]
    bite.extra_damage_dices.append(4)
    bite.extra_damage_dices_numbers.append(1)
    bite.extra_damage_type.append(DamageType.FIRE)
    bite.extra_damage_bonus.append(bonuses[0])
    entity.equipment.extra_attack_damage_dices.append(4)
    entity.equipment.extra_attack_damage_dices_numbers.append(1)
    entity.equipment.extra_attack_damage_type.append(DamageType.FIRE)
    entity.equipment.extra_attack_damage_bonus.append(bonuses[1])
    entity.spellcasting.extra_spell_damage_dices.append(4)
    entity.spellcasting.extra_spell_damage_dices_numbers.append(1)
    entity.spellcasting.extra_spell_damage_type.append(DamageType.FIRE)
    entity.spellcasting.extra_spell_damage_bonus.append(bonuses[2])
    for bonus in bonuses:
        removed.update(value_identities(bonus))
    retained = ModifiableValue.create(source_entity_uuid=entity.uuid, base_value=3, value_name='Independent')
    bonuses[0].from_target_static = retained.to_target_static
    kept = value_identities(retained)
    sword = give(entity, 'weapon.circus.flaming_scimitar')
    assert sword.extra_damage_bonus
    for bonus in sword.extra_damage_bonus:
        kept.update(value_identities(bonus))
    prepared = release(game, entity)
    assert prepared is not None
    assert all(still_registered(identity) for identity in removed | kept)
    game.commit_entity_retirement(prepared)
    assert not any(still_registered(identity) for identity in removed)
    assert all(still_registered(identity) for identity in kept)
    assert get_map().get_object_position(sword.uuid) == (2, 2)


def test_retirement_preserves_uuid_coat_charges_container_contents_and_causal_drops():
    game = Game()
    entity = actor(game)
    other = actor(game, 'Recipient', (3, 2))
    dagger = give(entity, 'weapon.dagger', WeaponSlot.MELEE_MAIN)
    coat = build_timed_fire_weapon_coat(entity.uuid, rounds=3)
    assert entity.loot_item(coat)
    assert not execute_use_action(entity, coat.uuid, 'Coat Main Hand').canceled
    coating = dagger.active_conditions['Flaming Coat']
    charged = give(entity, 'consumable.weapon_coat.fire')
    original_charges = charged.charges
    container = StorageChest(source_entity_uuid=entity.uuid, item_id='test.portable_storage', is_pickable=True)
    content = build_authored_item('weapon.shortsword', entity.uuid)
    assert container.chest_inventory.add_item(content)
    assert entity.loot_item(container)
    parent = Event(source_entity_uuid=entity.uuid, name='Expiry', event_type=EventType.CONDITION_REMOVAL)
    cursor = EventQueue.event_cursor()
    prepared = release(game, entity, parent=parent)
    assert prepared is not None
    assert entity.equipment.get_weapon(WeaponSlot.MELEE_MAIN) is dagger
    game.commit_entity_retirement(prepared)
    assert game.get_entity(entity.uuid) is Entity.get(entity.uuid) is BaseBlock.get(entity.uuid) is None
    assert get_map().get_entity_position(entity.uuid) is None
    for item in (dagger, charged, container):
        assert BaseBlock.get(item.uuid) is item
        assert get_map().get_object_position(item.uuid) == (2, 2)
        assert item.owner_uuid is item.stored_in_uuid is None
    assert dagger.active_conditions['Flaming Coat'] is coating and coating.applied
    assert charged.charges == original_charges
    assert container.chest_inventory.items[content.uuid] is content
    assert BaseBlock.get(content.uuid) is content
    assert other.loot_item(dagger) and other.equip_item(dagger.uuid, WeaponSlot.MELEE_MAIN)
    assert dagger.active_conditions['Flaming Coat'] is coating
    events = [event for _, event in EventQueue.iter_events_since(cursor)
              if event.phase is EventPhase.COMPLETION]
    assert not any(event.event_type is EventType.ITEM_DESTRUCTION for event in events)
    drops = [event for event in events if isinstance(event, ItemLocationStateEvent)
             and event.location is ItemLocation.FLOOR]
    assert {event.item_state.item_uuid for event in drops} == {dagger.uuid, charged.uuid, container.uuid}
    assert all(event.parent_lineage == parent.lineage_uuid for event in drops)
    count = EventQueue.event_cursor()
    game.commit_entity_retirement(prepared)
    assert EventQueue.event_cursor() == count
    assert release(game, entity) is None


def test_intrinsic_items_and_owned_actions_retire_without_loot_or_destroy_events():
    game = Game()
    entity = Entity.create(source_entity_uuid=uuid4(), name='Wolf')
    bite = build_authored_item('weapon.creature.wolf_bite', entity.uuid)
    hide = build_authored_item('armor.creature.wolf_natural', entity.uuid)
    entity.install_initial_items(((bite, WeaponSlot.MELEE_MAIN), (hide, BodyPart.BODY)))
    attack = Attack(source_entity_uuid=entity.uuid, weapon_slot=WeaponSlot.MELEE_MAIN, template=True)
    entity.register_action(attack)
    entity.compose_entity()
    game.deploy_entity(entity, (2, 2))
    cursor = EventQueue.event_cursor()
    token = release(game, entity)
    assert token is not None
    game.commit_entity_retirement(token)
    for item in (bite, hide):
        assert BaseBlock.get(item.uuid) is None
        assert get_map().get_object_position(item.uuid) is None
    assert BaseObject.get(attack.uuid) is None
    assert not entity.registered_actions
    assert all(event.event_type is not EventType.ITEM_DESTRUCTION
               for _, event in EventQueue.iter_events_since(cursor))


@pytest.mark.parametrize('cause', (SummonDepartureCause.DISMISSED, SummonDepartureCause.EXPIRED))
def test_only_mandatory_ending_bypasses_owned_condition_veto(cause):
    game = Game()
    entity = actor(game)
    item = give(entity, 'weapon.dagger', WeaponSlot.MELEE_MAIN)
    condition = Blinded(source_entity_uuid=entity.uuid, target_entity_uuid=entity.uuid)
    entity.add_condition(condition)
    def veto(event, source):
        if isinstance(event, ConditionRemovalEvent):
            return event.cancel(status_message='Keep condition')
        return None
    entity.add_event_handler(EventHandler(name='Veto', source_entity_uuid=entity.uuid,
        event_processor=veto, trigger_conditions=[Trigger(event_type=EventType.CONDITION_REMOVAL,
            event_phase=EventPhase.DECLARATION)]))
    token = release(game, entity, cause)
    if cause is SummonDepartureCause.DISMISSED:
        assert token is None
        assert game.get_entity(entity.uuid) is entity
        assert entity.active_conditions['Blinded'] is condition
        assert entity.equipment.get_weapon(WeaponSlot.MELEE_MAIN) is item
    else:
        assert token is not None
        game.commit_entity_retirement(token)
        assert Entity.get(entity.uuid) is None
        assert not condition.applied
        assert BaseBlock.get(item.uuid) is item


def test_item_retire_reports_rejected_owned_condition_without_partial_membership_loss():
    game = Game()
    entity = actor(game)
    dagger = give(entity, 'weapon.dagger', WeaponSlot.MELEE_MAIN)
    coat = build_timed_fire_weapon_coat(entity.uuid, rounds=3)
    assert entity.loot_item(coat)
    assert not execute_use_action(entity, coat.uuid, 'Coat Main Hand').canceled
    condition = dagger.active_conditions['Flaming Coat']
    def veto(event, source):
        if isinstance(event, ConditionRemovalEvent):
            return event.cancel(status_message='Keep condition')
        return None
    dagger.add_event_handler(EventHandler(name='Veto', source_entity_uuid=entity.uuid,
        event_processor=veto, trigger_conditions=[Trigger(event_type=EventType.CONDITION_REMOVAL,
            event_phase=EventPhase.DECLARATION)]))
    assert not dagger.retire()
    assert dagger.owner_uuid == entity.uuid
    assert entity.equipment.get_weapon(WeaponSlot.MELEE_MAIN) is dagger
    assert dagger.active_conditions['Flaming Coat'] is condition
    assert BaseBlock.get(dagger.uuid) is dagger


def test_retirement_does_not_sweep_independent_effects_with_same_source_uuid():
    game = Game()
    entity = actor(game)
    recipient = actor(game, 'Recipient', (3, 2))
    effect = Blinded(source_entity_uuid=entity.uuid, target_entity_uuid=recipient.uuid)
    recipient.add_condition(effect)
    unrelated = BaseItem(source_entity_uuid=entity.uuid, item_id='test.unrelated', name='Independent object')
    unrelated.place_on_grid((4, 2))
    token = release(game, entity)
    assert token is not None
    game.commit_entity_retirement(token)
    assert recipient.active_conditions['Blinded'] is effect and effect.applied
    assert BaseBlock.get(unrelated.uuid) is unrelated
    assert get_map().get_object_position(unrelated.uuid) == (4, 2)


@pytest.mark.parametrize('cause', (SummonDepartureCause.DISMISSED, SummonDepartureCause.EXPIRED))
def test_equipment_veto_preserves_voluntary_actor_but_not_expired_authority(cause):
    game = Game()
    entity = actor(game)
    item = give(entity, 'weapon.dagger', WeaponSlot.MELEE_MAIN)
    def veto(event, source):
        return event.cancel(status_message='Retain equipment')
    entity.add_event_handler(EventHandler(name='Equipment veto', source_entity_uuid=entity.uuid,
        validation_only=True, event_processor=veto, trigger_conditions=[Trigger(
            event_type=EventType.WEAPON_UNEQUIP, event_phase=EventPhase.EXECUTION)]))
    prepared = release(game, entity, cause)
    if cause is SummonDepartureCause.DISMISSED:
        assert prepared is None
        assert entity.equipment.get_weapon(WeaponSlot.MELEE_MAIN) is item
        assert get_map().get_entity_position(entity.uuid) == (2, 2)
    else:
        assert prepared is not None
        game.commit_entity_retirement(prepared)
        assert Entity.get(entity.uuid) is None
        assert get_map().get_object_position(item.uuid) == (2, 2)


def test_observer_failure_does_not_leave_live_actor_or_lose_real_possession(caplog):
    game = Game()
    entity = actor(game)
    item = give(entity, 'weapon.dagger', WeaponSlot.MELEE_MAIN)
    prepared = release(game, entity)
    assert prepared is not None
    def observer(event):
        if event.event_type is EventType.WEAPON_UNEQUIP:
            raise RuntimeError('observer failed')
    EventQueue.add_on_event_callback(observer)
    try:
        game.commit_entity_retirement(prepared)
        assert 'observer failed' in caplog.text
    finally:
        EventQueue.remove_on_event_callback(observer)
    assert Entity.get(entity.uuid) is BaseBlock.get(entity.uuid) is game.get_entity(entity.uuid) is None
    assert get_map().get_entity_position(entity.uuid) is None
    assert get_map().get_object_position(item.uuid) == (2, 2)
    assert BaseBlock.get(item.uuid) is item
    game.commit_entity_retirement(prepared)


def test_actor_retirement_releases_attached_light():
    game = Game()
    entity = actor(game)
    light = get_map().add_light_source(entity.position, bright_radius_feet=5, dim_radius_feet=0,
        anchor_uuid=entity.uuid)
    prepared = release(game, entity)
    assert prepared is not None
    game.commit_entity_retirement(prepared)
    assert get_map().get_light_source_position(light) is None


@pytest.mark.parametrize('change', ('unequip', 'equip', 'reslot'))
def test_retirement_rejects_changed_container_or_exact_equipment_slot(change):
    game = Game()
    entity = actor(game)
    dagger = give(entity, 'weapon.dagger', None if change == 'equip' else WeaponSlot.MELEE_MAIN)
    prepared = release(game, entity, SummonDepartureCause.DISMISSED)
    assert prepared is not None
    if change == 'unequip':
        assert entity.unequip_item(WeaponSlot.MELEE_MAIN)
    elif change == 'equip':
        assert entity.equip_item(dagger.uuid, WeaponSlot.MELEE_MAIN)
    else:
        assert entity.unequip_item(WeaponSlot.MELEE_MAIN)
        assert entity.equip_item(dagger.uuid, WeaponSlot.MELEE_OFF)
    assert not entity.validate_prepared_retirement(prepared.entity)
    entity.cancel_retirement(prepared.entity)
    assert game.get_entity(entity.uuid) is entity
    assert dagger.owner_uuid == entity.uuid
    assert get_map().get_object_position(dagger.uuid) is None
