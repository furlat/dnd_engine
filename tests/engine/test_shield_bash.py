"""An authored shield attack uses real equipped gear and the native attack budget."""

from uuid import uuid4

import pytest

from dnd.actions import Attack, AttackEvent
from dnd.actions_functional import setup_standard_actions
from dnd.blocks.health import HealthConfig
from dnd.content.items.authored_item_builders import build_authored_item
from dnd.core.action_types import ActionSelection, ActionVariantFacet
from dnd.core.creature_types import DamageType, Size
from dnd.core.dice import AttackOutcome, fixed_dice_faces
from dnd.core.equipment_types import WeaponKind, WeaponSlot, WeaponSet
from dnd.core.events import EventHandler, EventPhase, EventQueue, EventType, Trigger
from dnd.core.modifiers import NumericalModifier
from dnd.core.values import Channel, Kind, add_modifier
from dnd.entity import Entity, EntityConfig
from dnd.game import Game
from dnd.monsters.traits import (
    AttackReplacement, MultiattackAction, ShieldBash, register_brute, register_shield_bash,
)
from dnd.runtime_reset import reset_engine_runtime


@pytest.fixture
def game():
    reset_engine_runtime(grid_size=(12, 10))
    result = Game()
    yield result
    result.close()
    reset_engine_runtime(grid_size=(12, 10))


def actor(game, name, position, *, size=Size.MEDIUM):
    entity = Entity.create(uuid4(), name, config=EntityConfig(faction=name, size=size,
        health=HealthConfig(max_hit_points_bonus=100)))
    entity.compose_entity()
    game.deploy_entity(entity, position)
    setup_standard_actions(entity)
    Entity.update_all_entities_senses()
    return entity


def equip(owner, item_id, slot):
    item = build_authored_item(item_id, owner.uuid)
    assert owner.loot_item(item) and owner.equip_item(item.uuid, slot)
    return item


def setup_bash(game, *, size=Size.MEDIUM):
    owner = actor(game, 'Owner', (3, 3))
    target = actor(game, 'Target', (4, 3), size=size)
    equip(owner, 'weapon.longsword', WeaponSlot.MELEE_MAIN)
    shield = equip(owner, 'shield.shield', WeaponSlot.MELEE_OFF)
    register_brute(owner)
    register_shield_bash(owner)
    return owner, target, shield


def bash_multiattack(owner):
    """Three longsword attacks, one of which the shield bash may replace."""
    return MultiattackAction(source_entity_uuid=owner.uuid, template=True,
        attack_sequence=((WeaponSlot.MELEE_MAIN, 3),),
        attack_replacement=AttackReplacement(sequence_index=0, weapon_kind=WeaponKind.LONGSWORD,
            action=ShieldBash(source_entity_uuid=owner.uuid)))


def perform_bash(owner, target, faces):
    template = owner.get_action_template('Shield Bash')
    with fixed_dice_faces(*faces):
        result = owner.perform(template, ActionSelection(template_uuid=template.uuid,
            target_uuids=(target.uuid,)))
    assert isinstance(result, AttackEvent)
    return result


@pytest.mark.parametrize('size', [Size.TINY, Size.SMALL, Size.MEDIUM])
def test_shield_bash_fixed_baseline_real_source_and_saved_prone(game, size):
    owner, target, shield = setup_bash(game, size=size)
    before = EventQueue.event_cursor()
    row = next(row for row in owner.get_available_actions().entity_actions
        if row.display_name == 'Shield Bash')
    assert row.outcome_profile.attack_bonus == 7
    profile = row.outcome_profile.damage_rolls[0]
    assert (profile.dice_count, profile.die_size, profile.flat_bonus, profile.damage_type) == (2, 4, 4, DamageType.BLUDGEONING.value)
    assert EventQueue.event_cursor() == before
    result = perform_bash(owner, target, (15, 2, 3, 2))
    assert not result.canceled and result.attack_outcome is AttackOutcome.HIT
    assert result.attack_bonus.normalized_score == 7
    assert target.get_hp() == 91 and 'Prone' in target.active_conditions
    assert result.source_item_uuid == shield.uuid and result.source_item_presentation.item_id == shield.item_id
    assert result.natural_weapon is None and result.shield_attack.item_uuid == shield.uuid
    assert result.attack_source_kind == 'equipped'
    assert len(result.damages) == 1  # Brute must not add another shield die.
    assert result.damages[0].damage_type is DamageType.BLUDGEONING
    assert result.damage_rolls[0].results == [2, 3]
    assert owner.action_economy.actions.normalized_score == 0
    assert owner.action_economy.bonus_actions.normalized_score == 1
    rolls = [event for event in EventQueue.get_events_by_type(EventType.DAMAGE_ROLL_RESULT)
        if event.phase is EventPhase.COMPLETION]
    assert len(rolls) == 1 and rolls[0].source_item_uuid == shield.uuid


@pytest.mark.parametrize('size', [Size.LARGE, Size.HUGE, Size.GARGANTUAN])
def test_large_target_takes_bash_damage_without_prone_save_or_noop_rider_events(game, size):
    owner, target, _ = setup_bash(game, size=size)
    before = EventQueue.event_cursor()
    result = perform_bash(owner, target, (15, 2, 3))
    assert not result.canceled and target.get_hp() == 91
    assert 'Prone' not in target.active_conditions
    assert not any(event.event_type is EventType.SAVING_THROW
        for _, event in EventQueue.iter_events_since(before))


@pytest.mark.parametrize('faces, outcome, hp, prone', [
    ((15, 2, 3, 20), AttackOutcome.HIT, 91, False),
    ((1,), AttackOutcome.CRIT_MISS, 100, False),
    ((20, 1, 1, 1, 1, 2), AttackOutcome.CRIT, 92, True),
])
def test_shield_bash_saves_misses_and_native_critical_dice(game, faces, outcome, hp, prone):
    owner, target, _ = setup_bash(game)
    result = perform_bash(owner, target, faces)
    assert not result.canceled and result.attack_outcome is outcome
    assert target.get_hp() == hp
    assert ('Prone' in target.active_conditions) is prone


def test_shield_bash_uses_independent_attack_damage_buffs_without_unarmed_bonuses(game):
    owner, target, _ = setup_bash(game)
    for value, bonus in ((owner.equipment.attack_bonus, 2), (owner.equipment.damage_bonus, 3),
            (owner.equipment.unarmed_attack_bonus, 50), (owner.equipment.unarmed_damage_bonus, 50)):
        add_modifier(value, Channel.SELF_STATIC, Kind.VALUE,
            NumericalModifier(name='Independent effect', value=bonus, source_entity_uuid=owner.uuid))
    result = perform_bash(owner, target, (15, 2, 3, 20))
    assert not result.canceled
    assert result.attack_bonus.normalized_score == 9
    assert target.get_hp() == 88


@pytest.mark.parametrize('release', ['unequip', 'transfer'])
def test_unwielded_or_transferred_shield_cannot_bash_and_does_not_spend_action(game, release):
    owner, target, shield = setup_bash(game)
    assert owner.unequip_item(WeaponSlot.MELEE_OFF) is shield
    if release == 'transfer':
        receiver = actor(game, 'Receiver', (3, 4))
        assert owner.inventory.transfer_to(shield.uuid, receiver.inventory)
        assert receiver.equip_item(shield.uuid, WeaponSlot.MELEE_OFF)
    row = next(row for row in owner.get_available_actions().entity_actions
        if row.display_name == 'Shield Bash')
    assert not row.valid_targets
    result = perform_bash(owner, target, ())
    assert result.canceled and target.get_hp() == 100
    assert owner.action_economy.actions.normalized_score == 1


@pytest.mark.parametrize('phase', [EventPhase.DECLARATION, EventPhase.EXECUTION])
def test_replacing_shield_during_attack_cannot_use_stale_declared_item(game, phase):
    owner, target, original = setup_bash(game)
    replacement = build_authored_item('shield.shield', owner.uuid)
    assert owner.loot_item(replacement)
    changed = []

    def swap(event, _source):
        if changed or (phase is EventPhase.EXECUTION and event.attack_bonus is None):
            return None
        changed.append(True)
        assert owner.unequip_item(WeaponSlot.MELEE_OFF) is original
        assert owner.equip_item(replacement.uuid, WeaponSlot.MELEE_OFF)
        return None

    owner.add_event_handler(EventHandler(source_entity_uuid=owner.uuid,
        trigger_conditions=[Trigger(event_type=EventType.ATTACK, event_phase=phase,
            event_source_entity_uuid=owner.uuid)], event_processor=swap))
    result = perform_bash(owner, target, ())
    assert result.canceled and target.get_hp() == 100
    assert result.source_item_uuid == original.uuid
    assert owner.equipment.get_equipped_shield() is replacement
    assert owner.action_economy.actions.normalized_score == (1 if phase is EventPhase.DECLARATION else 0)


def test_shield_bash_replaces_exactly_one_attack_in_existing_multiattack_budget(game):
    owner, target, _ = setup_bash(game)
    action = bash_multiattack(owner)
    owner.register_action(action)
    row = next(row for row in owner.get_available_actions().entity_actions
        if row.behavior_id == 'action.monster.multiattack' and row.variant_facets)
    assert row.variant_facets == (ActionVariantFacet(key='form', value='substitution', label='Shield Bash'),)
    with fixed_dice_faces(15, 2, 3, 20, 15, 2, 3, 15, 2, 3):
        result = owner.perform(action, ActionSelection(template_uuid=action.uuid,
            target_uuids=(target.uuid,), facets=row.variant_facets))
    assert result is not None and not result.canceled
    attacks = [event for event in EventQueue.get_events_by_type(EventType.ATTACK)
        if event.phase is EventPhase.COMPLETION]
    assert len(attacks) == 3 and sum(event.shield_attack is not None for event in attacks) == 1
    assert owner.action_economy.actions.normalized_score == 0
    assert owner.action_economy.bonus_actions.normalized_score == 1
    assert all(not event.costs for event in attacks)


def test_shield_substitution_disappears_without_shield_and_rejects_stale_choice(game):
    owner, target, shield = setup_bash(game)
    action = bash_multiattack(owner)
    owner.register_action(action)
    assert owner.unequip_item(WeaponSlot.MELEE_OFF) is shield
    choices = [row.variant_facets for row in owner.get_available_actions().entity_actions
        if row.behavior_id == 'action.monster.multiattack']
    assert choices == [()]
    result = owner.perform(action, ActionSelection(template_uuid=action.uuid,
        target_uuids=(target.uuid,), facets=(ActionVariantFacet(key='form', value='substitution', label='Shield Bash'),)))
    assert result is not None and result.canceled
    assert target.get_hp() == 100 and owner.action_economy.actions.normalized_score == 1


def test_shield_bash_uses_native_switch_on_attack_policy(game):
    owner, target, _ = setup_bash(game)
    equip(owner, 'weapon.longbow', WeaponSlot.RANGED_MAIN)
    owner.equipment.active_weapon_set = WeaponSet.RANGED
    result = perform_bash(owner, target, (15, 2, 3, 20))
    assert not result.canceled and target.get_hp() == 91
    assert owner.equipment.active_weapon_set is WeaponSet.MELEE
